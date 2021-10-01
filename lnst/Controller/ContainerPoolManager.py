import subprocess
import logging
import socket
from time import sleep
from json import loads
from podman.domain.containers import Container
from podman.domain.networks import Network
from podman.errors import APIError
from podman import PodmanClient
from lnst.Controller.SlavePoolManager import PoolManagerError
from lnst.Controller.Machine import Machine


class ContainerPoolManager(object):
    """This class implements managing containers and networks.
    It uses Podman API to handle operations with containers,
    the API needs to be running with root privileges.
    """

    def __init__(
        self, pools, msg_dispatcher, ctl_config, podman_uri, image, pool_checks=True
    ):
        self._pool = {}
        self._machines = {}
        self._containers = {}
        self._msg_dispatcher = msg_dispatcher
        self._ctl_config = ctl_config

        self._podman_client = None
        self._image = ""
        self._podman_connect(podman_uri)
        self.image = image

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
            client = PodmanClient(base_url=podman_uri)
            client.info()  # info() will try to connect to the API
        except APIError as e:
            raise PoolManagerError(f"Could not connect to Podman API: {e}")

        self._podman_client = client

    def _check_machine(self, machine: Machine):
        """Method checks if the slave process inside of the container is running."""
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

            logging.debug(f"Connected to slave process at machine {hostname}")
            break  # successfully connected
        else:
            raise PoolManagerError(f"Could not connect to machine {hostname}")

        err = connection.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        if err:
            connection.close()
            raise PoolManagerError(f"Could not connect to machine {hostname}")

        connection.shutdown(socket.SHUT_RDWR)
        connection.close()

        logging.info(f"Slave process is running at {hostname}")

    @staticmethod
    def _start_container(container: Container, machine: Machine):
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
            )  # checks if the slave process is already running

        self._pool[name]["params"]["hostname"] = machine.get_hostname()

        return container, machine

    def _create_network(self, network_name: str):
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

    def _connect_to_network(self, container: Container, network: Network):
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

    def _connect_to_networks(self, container: Container, network_reqs: dict):
        for _, params in network_reqs["interfaces"].items():
            name = params["network"]
            logging.debug(f"Connecting {container.name} to {name}")

            network = self._create_network(name)

            self._connect_to_network(container, network)

    def process_reqs(self, mreqs: dict):
        for m_id, m_reqs in mreqs.items():
            container, machine = self._create_container(m_id, m_reqs)
            self._connect_to_networks(container, m_reqs)

            self._machines[m_id] = machine
            self._containers[m_id] = container
            machine.init_connection()

    def cleanup_containers(self):
        logging.info("Cleaning containers")

        for m_id, container in self._containers.items():
            logging.debug("Stopping container " + m_id)
            container.stop()

            logging.debug("Removing container " + m_id)
            container.remove()

    def cleanup_networks(self):
        for name, network in self._networks.items():
            logging.debug("Removing network " + name)
            try:
                network.remove(force=True)
            except APIError as e:
                logging.error(f"Could not remove network {name}: {e}")

    def cleanup(self):
        self.cleanup_containers()
        self.cleanup_networks()
