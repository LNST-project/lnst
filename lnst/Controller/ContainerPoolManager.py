import subprocess
import logging
import socket
from time import sleep
from json import loads
from typing import Optional, Union
from lnst.Controller.AgentPoolManager import PoolManagerError
from lnst.Controller.Machine import Machine
from lnst.Common.DependencyError import DependencyError


class ContainerPoolManager(object):
    """This class implements managing containers and networks.
    It uses Podman API to handle operations with containers,
    the API needs to be running with root privileges.

    :param pools:
        Dictionary that contains pools.
        In :py:class:`lnst.Controller.ContainerPoolManager.ContainerPoolManager`
        are pools dynamically created based on recipe requirements.
        That means this parameter is not used but it is needed to keep parameters of this class and
        :py:class:`lnst.Controller.AgentPoolManager.AgentPoolManager` the same.
    :type pools: dict

    :param msg_dispatcher:
    :type msg_dispatcher: :py:class:`lnst.Controller.MessageDispatcher.MessageDispatcher`

    :param ctl_config:
    :type ctl_config: :py:class:`lnst.Controller.Config.CtlConfig`

    :param pool_checks:
        if False, will disable checking the online status of Agents
    :type pool_checks: boolean (default True)

    :param podman_uri:
        Mandatory parameter
    :type podman_uri: str

    :param image:
        Mandatory parameter
    :type image: str

    :param network_plugin:
        Podman network plugin, 'cni', 'netavark' or 'custom_lnst', if unset, the network backend is auto-detected
    :type network_plugin: Optional[str]
    """

    def __init__(
        self, pools, msg_dispatcher, ctl_config, podman_uri, image,
        network_plugin='netavark', pool_checks=True
    ):
        self._import_optionals()
        self._pool = {}
        self._machines = {}
        self._containers = {}
        self._msg_dispatcher = msg_dispatcher
        self._ctl_config = ctl_config

        self._podman_client = None
        self._image = ""
        self._podman_connect(podman_uri)
        self.image = image
        self.network_plugin = network_plugin

        self._networks = {}
        self._network_prefix = "lnst_container_net_"
        self._start_timeout = 5
        self._pool_check = pool_checks

    @property
    def image(self):
        return self._image

    @image.setter
    def image(self, name):
        if not self._podman_client.images.exists(name):
            raise PoolManagerError("Provided image does not exists!")

        self._image = name

    @staticmethod
    def _import_optionals():
        try:
            global APIError
            global Container
            global Network
            global IPAMConfig

            from podman.errors import APIError
            from podman.domain.containers import Container
            from podman.domain.networks import Network
            from podman.domain.ipam import IPAMConfig

        except ModuleNotFoundError as e:
            raise DependencyError(e)

    def get_pool(self):
        return self.get_pools()["default"]

    def get_pools(self):
        return {
            "default": self._pool
        }  # `ContainerPoolManager` does not support multiple pools

    def get_machine_pools(self):
        return {"default": self._machines}

    def get_machine_pool(self, pool_name):
        return self._machines

    def get_networks(self):
        return self._networks

    def get_network_name(self, network: str):
        return self._network_prefix + network

    def get_original_network_name(self, network: str):
        return network[len(self._network_prefix) :]

    def _podman_connect(self, podman_uri: str):
        logging.debug("Connecting to Podman API")
        try:
            from podman import PodmanClient
            client = PodmanClient(base_url=podman_uri, timeout=60)
            client.info()  # info() will try to connect to the API
        except ModuleNotFoundError as e:
            raise DependencyError(e)
        except APIError as e:
            raise PoolManagerError(f"Could not connect to Podman API: {e}")

        self._podman_client = client

    def _check_machine(self, machine: Machine):
        """Method checks if the agent process inside of the container is running."""
        hostname = machine.get_hostname()
        logging.debug(f"Checking connection with machine {hostname}")
        connection = socket.socket()
        connection.settimeout(self._start_timeout)

        retry_counter = 5

        for i in range(retry_counter):
            logging.debug(f"Connecting to {machine.get_hostname()}, retry counter: {i}")
            try:
                connection.connect((hostname, machine._port))
            except (ConnectionRefusedError, ConnectionAbortedError):
                sleep(1)
                continue

            logging.debug(f"Connected to agent process at machine {hostname}")
            break  # successfully connected
        else:
            raise PoolManagerError(f"Could not connect to machine {hostname}")

        err = connection.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        if err:
            connection.close()
            raise PoolManagerError(f"Could not connect to machine {hostname}")

        connection.shutdown(socket.SHUT_RDWR)
        connection.close()

        logging.info(f"Agent process is running at {hostname}")

    @staticmethod
    def _start_container(container: "Container", machine: Machine):
        logging.debug("Starting container " + container.name)
        container.start()

        container.reload()
        container.wait(condition="running")
        machine._hostname = container.attrs["NetworkSettings"]["Networks"]["podman"][
            "IPAddress"
        ]

    def _create_container(self, name: str, reqs: dict):
        logging.info("Creating container " + name)

        if "rpc_port" in reqs:
            rpc_port = reqs["rpc_port"]
        else:
            rpc_port = None

        self._pool[name] = {
            "interfaces": {},
            "params": {"hostname": "", "rpc_port": rpc_port},
            "security": {"auth_type": "none"},
            "available": True,
        }

        try:
            container = self._podman_client.containers.create(
                self.image, hostname=name, privileged=True
            )
        except APIError as e:
            raise PoolManagerError(f"Could not create container {name}: {e}")

        machine = Machine(
            name,
            "",
            self._msg_dispatcher,
            self._ctl_config,
            None,
            rpc_port,
            self._pool[name]["security"],
            reqs,
        )  # to get hostname the container needs to run

        self._start_container(container, machine)
        if self._pool_check:
            self._check_machine(
                machine
            )  # checks if the agent process is already running

        self._pool[name]["params"]["hostname"] = machine.get_hostname()

        return container, machine

    def _create_network(self, network_name: str, plugin: Optional[str]):
        if not plugin:
            podman_info = self._podman_client.info()
            plugin = podman_info["host"]["networkBackend"]

        logging.debug(f"Using {plugin} network backend for containers")

        if plugin == "netavark":
            return self._create_network_netavark(network_name)
        elif plugin == "cni":
            return self._create_network_cni(network_name)
        elif plugin == "custom_lnst":
            return self._create_network_custom_lnst(network_name)
        else:
            raise PoolManagerError(f"Unknown podman network plugin {plugin}")

    def _create_network_cni(self, network_name: str):
        """Networks are created "manually" because podman does not
        support creating L2 [1] networks. IPs in these networks are managed
        by controller.

        [1] https://www.cni.dev/plugins/v1.0/main/bridge/#example-l2-only-configuration
        """
        name = self.get_network_name(network_name)
        if name in self._networks:
            return self._networks[name]

        logging.info(f"Creating network {name}")
        try:
            with open(f"/etc/cni/net.d/{name}.conflist", "w") as config:
                config.write(
                    '''{
                    "cniVersion": "0.4.0",
                    "name": "'''
                    + name
                    + """",
                    "plugins": [
                    {
                        "bridge": "cni-podman1",
                        "hairpinMode": true,
                        "ipam": {},
                        "isGateway": false,
                        "type": "bridge"
                    }
                ]
        }
"""
                )
            network = self._podman_client.networks.get(name)
        except APIError as e:
            raise PoolManagerError(f"Could not create network {name}: {e}")
        except IOError as e:
            raise PoolManagerError(f"Could not create network configuration file: {e}")

        self._networks[name] = network

        return network

    def _create_network_netavark(self, network_name: str):
        name = self.get_network_name(network_name)
        if name in self._networks:
            return self._networks[name]

        ipam_config = IPAMConfig(
            driver="none",
        )
        logging.info(f"Creating network {name}")
        try:
            self._podman_client.networks.create(
                name,
                internal=True,
                enable_ipv6=True,
                ipam=ipam_config,
            )
            network = self._podman_client.networks.get(name)
        except APIError as e:
            raise PoolManagerError(f"Could not create network {name}: {e}")
        except IOError as e:
            raise PoolManagerError(f"Could not create network configuration file: {e}")

        self._networks[name] = network

        return network

    def _create_network_custom_lnst(self, network_name: str):
        name = self.get_network_name(network_name)
        if name in self._networks:
            return self._networks[name]

        br_name = self._generate_bridge_name()

        try:
            res = subprocess.run(
                f"ip -j link add name {br_name} type bridge",
                check=True,
                shell=True,
                stdout=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            raise PoolManagerError(f"Could not create network {name}: {e}")

        try:
            res = subprocess.run(
                f"ip link set {br_name} up",
                check=True,
                shell=True,
                stdout=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            raise PoolManagerError(f"Could not UP network {name}: {e}")

        self._networks[name] = network = {'name': name, 'br_name': br_name, 'out': res, "nics": []}
        return network


    def _connect_to_network(self, container: "Container", network: Union[dict, "Network"]):
        if isinstance(network, Network):
            return self._connect_to_podman_network(container, network)
        elif isinstance(network, dict):
            return self._connect_to_custom_network(container, network)
        else:
            raise PoolManagerError("Unknown network type")

    def _connect_to_podman_network(self, container: "Container", network: "Network"):
        """There is no way to get MAC address of remote interface except
        executing "ip l" inside container.
        """
        logging.debug(f"Connecting {container.name} to {network.name}")
        try:
            network.connect(container)
        except APIError:
            raise PoolManagerError(
                f"Could not connect {container.name} to {network.name}"
            )

        container.reload()

        logging.debug(
            f"Getting MAC address of remote interface at {container.name} for {network.name}"
        )
        interfaces = loads(
            subprocess.check_output(
                ["podman", "exec", "-it", container.name, "ip", "-j", "a"]
            ).decode("utf-8")
        )
        interface = max(
            interfaces, key=(lambda inf: inf["ifindex"])
        )  # get interface with highest index

        eth = interface["ifname"]
        if "link_index" in interface:
            eth += f"@{interface['link_index']}"

        machine = self._pool[container.attrs["Config"]["Hostname"]]
        machine["interfaces"][eth] = {
            "params": {"hwaddr": interface["address"], "driver": "veth"},
            "network": network.name,
        }

        return True

    def _connect_to_custom_network(self, container: "Container", network: dict):
        logging.debug(f"Connecting {container.name} to {network['name']}")
        nic_root_name, nic_container_name = self._generate_nic_name_pair(network)
        try:
            res = subprocess.run(
                f"ip link add {nic_root_name} type veth peer name {nic_container_name}",
                check=True,
                shell=True,
                stdout=subprocess.PIPE
            )
            network['nics'].append(nic_root_name)
            network['nics'].append(nic_container_name)
        except subprocess.CalledProcessError as e:
            raise PoolManagerError(
                f"Could not create veth pair for {container.name} to {network['name']}"
            )

        try:
            res = subprocess.run(
                f"ip link set {nic_container_name} netns {container.attrs['NetworkSettings']['SandboxKey']}",
                check=True,
                shell=True,
                stdout=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            raise PoolManagerError(
                f"Could not move veth {nic_container_name} into {container.name}"
            )

        try:
            res = subprocess.run(
                f"ip link set {nic_root_name} master {network['br_name']}",
                check=True,
                shell=True,
                stdout=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            raise PoolManagerError(
                f"Could not set veth {nic_root_name} as bridge port of {network['br_name']}"
            )

        try:
            res = subprocess.run(
                f"ip link set {nic_root_name} up",
                check=True,
                shell=True,
                stdout=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            raise PoolManagerError(
                f"Could not set veth {nic_root_name} up"
            )

        logging.debug(
            f"Getting MAC address of remote interface at {container.name} for {network['name']}"
        )
        interfaces = loads(
            subprocess.check_output(
                ["podman", "exec", "-it", container.name, "ip", "-j", "a"]
            ).decode("utf-8")
        )
        for i in interfaces:
            if i['ifname'] == nic_container_name:
                eth = i["ifname"]
                if "link_index" in i:
                    eth += f"@{i['link_index']}"
                machine = self._pool[container.attrs["Config"]["Hostname"]]
                machine["interfaces"][eth] = {
                    "params": {"hwaddr": i["address"], "driver": "veth"},
                    "network": network['name'],
                }

        return True

    def _generate_bridge_name(self):
        i = 0
        while True:
            name_candidate = f"br{i}"
            res = subprocess.run(
                f"ip link show {name_candidate}",
                shell=True,
                stdout=subprocess.PIPE,
            )
            if res.returncode == 1:
                return name_candidate
            i += 1

    def _generate_nic_name_pair(self, network: dict):
        i = 0
        while True:
            name_candidate_root = f"{network['br_name']}_nic{i}_r"
            name_candidate_container = f"{network['br_name']}_nic{i}_c"
            if name_candidate_root not in network['nics'] and name_candidate_container not in network['nics']:
                return name_candidate_root, name_candidate_container
            i += 1

    def _connect_to_networks(self, container: "Container", network_reqs: dict):
        for _, params in network_reqs["interfaces"].items():
            name = params["network"]
            logging.debug(f"Connecting {container.name} to {name}")

            network = self._create_network(name, self.network_plugin)

            self._connect_to_network(container, network)

    def process_reqs(self, mreqs: dict):
        """This method is called by :py:class:`lnst.Controller.MachineMapper.ContainerMapper`,
        it is responsible for creating containers and networks.
        """
        for m_id, m_reqs in mreqs.items():
            container, machine = self._create_container(m_id, m_reqs)
            self._connect_to_networks(container, m_reqs)

            self._machines[m_id] = machine
            self._containers[m_id] = container
            machine.init_connection()

    def cleanup_containers(self):
        logging.info("Cleaning containers")

        for m_id, container in self._containers.items():
            try:
                logging.debug("Stopping container " + m_id)
                container.stop()

                logging.debug("Removing container " + m_id)
                container.remove()
            except Exception as e:
                logging.exception(f"Error during container cleanup: {e}")

        self._containers = {}

    def cleanup_networks(self):
        for name, network in self._networks.items():
            logging.debug("Removing network " + name)

            if isinstance(network, Network):
                self._cleanup_podman_network(network)
            elif isinstance(network, dict):
                self._cleanup_custom_network(network)
            else:
                raise PoolManagerError(f"Can't cleanup this type of network {type(network)}")

        self._networks = {}

    def _cleanup_podman_network(self, network: "Network"):
        try:
            network.remove(force=True)
        except APIError as e:
            logging.error(f"Could not remove network {name}: {e}")

    def _cleanup_custom_network(self, network: dict):
        for nic in network['nics']:
            try:
                res = subprocess.run(
                    f"ip link del {nic}",
                    check=True,
                    shell=True,
                    stdout=subprocess.PIPE
                )
            except subprocess.CalledProcessError as e:
                logging.exception(
                    f"Could not delete nic {nic}: {e}"
                )

        try:
            res = subprocess.run(
                f"ip link del {network['br_name']}",
                check=True,
                shell=True,
                stdout=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            logging.exception(
                f"Could not delete network bridge {network['br_name']}: {e}"
            )


    def cleanup(self):
        self.cleanup_containers()
        self.cleanup_networks()
