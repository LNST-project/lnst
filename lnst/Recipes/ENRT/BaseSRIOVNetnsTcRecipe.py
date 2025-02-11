from collections.abc import Collection

from lnst.Common.Parameters import (
    Param,
    IPv4NetworkParam,
    IPv6NetworkParam,
)
from lnst.Common.IpAddress import interface_addresses
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Controller.NetNamespace import NetNamespace
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.RecipeCommon.Perf.Recipe import RecipeConf
from lnst.Recipes.ENRT.helpers import ip_endpoint_pairs
from lnst.Recipes.ENRT.BaremetalEnrtRecipe import BaremetalEnrtRecipe
from lnst.Recipes.ENRT.SRIOVDevices import SRIOVDevices
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin,
)


class BaseSRIOVNetnsTcRecipe(
    CommonHWSubConfigMixin, OffloadSubConfigMixin, BaremetalEnrtRecipe
):
    """
    This base class provides common network configuration for tests
    that aims for TC hardware offload testing.

    The class does following tasks that are common to these setups:
    * sets NICs to switchdev mode
    * prepare virtual functions and their representors
    * moves the virtual function device to network namespace
    * enables hardware offload on the PF and VF representor

    .. code-block:: none

                      +--------+
               +------+ switch +-------+
               |      +--------+       |
            +--|--+                 +--|--+
    +-------|eth0|-------+  +-------|eth0|-------+
    |       +----+       |  |       +----+       |
    |         |          |  |         |          |
    |   vf0_representor  |  |   vf0_representor  |
    |         |          |  |         |          |
    | +----------------+ |  | +----------------+ |
    | |       |        | |  | |       |        | |
    | |      vf0       | |  | |      vf0       | |
    | |                | |  | |                | |
    | |     netns      | |  | |     netns      | |
    | +----------------+ |  | +----------------+ |
    |                    |  |                    |
    |      host1         |  |       host2        |
    +--------------------+  +--------------------+

    All sub configurations are included via Mixin classes.

    The actual test machinery is implemented in the :any:`BaseEnrtRecipe` class.
    """
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    """
    This parameter was created due to the difference between various kernel and distro
    versions, not having consistent naming scheme of virtual function.

    Solution here is to expect deterministic VF name, which is derived from the PF name.
    With specific kernel parameter `biosdevname=1` we can expect default suffix on
    VF to be created to be `_n`, where n is the index of VF created.
    """
    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="off", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="on", gso="off", tso="off", tx="on", rx="on"),
        dict(gro="on", gso="on", tso="off", tx="off", rx="on"),
        dict(gro="on", gso="on", tso="on", tx="on", rx="off")))

    vf_net_ipv4 = IPv4NetworkParam(default="192.168.101.0/24")
    vf_net_ipv6 = IPv6NetworkParam(default="fc00::/64")

    def test_wide_configuration(self, config):
        """
        Test wide configuration for this recipe involves switching the device to switchdev
        mode, adding single VF and mapping the VF, as well as its representor.

        New namespace is created to mimic container networking, where the VF is moved.
        Next, VF is assigned an IPv4 and IPv6 address on both hosts.

        host1.eth0 = 192.168.101.1/24 and fc00::1/64

        host2.eth0 = 192.168.101.2/24 and fc00::2/64

        Derived classes has to implement :method:`add_tc_filter_rules`.

        The derived class can also override :method:`add_network_layers`.
        """
        host1, host2 = self.matched.host1, self.matched.host2
        config = super().test_wide_configuration(config)

        # create virtual functions
        for host in [host1, host2]:
            host.eth0.eswitch_mode = "switchdev"
            host.sriov_devices = SRIOVDevices(host.eth0, 1)
            vf_dev, vf_rep_dev = host.sriov_devices[0]

            host.newns = NetNamespace("lnst")
            host.newns.vf_eth0 = vf_dev

            host.run(f"ethtool -K {vf_rep_dev.name} hw-tc-offload on")
            host.run(f"ethtool -K {host.eth0.name} hw-tc-offload on")

        vf_ipv4_addr = interface_addresses(self.params.vf_net_ipv4)
        vf_ipv6_addr = interface_addresses(self.params.vf_net_ipv6)

        for host in [host1, host2]:
            vf_dev, vf_rep_dev = host.sriov_devices[0]
            config.configure_and_track_ip(vf_dev, next(vf_ipv4_addr))
            config.configure_and_track_ip(vf_dev, next(vf_ipv6_addr))

            for dev in [
                host.eth0,
                vf_dev,
                vf_rep_dev,
            ]:
                dev.up()

        self.wait_tentative_ips(config.configured_devices)

        self.add_network_layers(config)
        self.add_tc_filter_rules(config)

        return config

    def add_tc_filter_rules(self, config):
        """
        This method must be implemented by derived class.

        It should configure tc qdiscs and filters used to bypass the software
        path and instead use the tc hardware offload functionality of the
        network devices.

        The class has to store all devices for which the ingress qdiscs have
        been configured in `config.ingress_devices` list so that these can be
        removed automatically in :method:`test_wide_deconfiguration`.
        """
        raise NotImplementedError()

    def add_network_layers(self, config):
        """
        This method is called during test wide configuration and can be used to
        add additional network layers, for example tunnels to the setup.
        """
        return config

    def perf_test(self, recipe_conf: RecipeConf):
        result = super().perf_test(recipe_conf)
        self._dump_tc_rules()

        return result

    def _dump_tc_rules(self):
        for dev in self.dump_tc_rules_devices:
            dev.host.run(f"tc -s filter show dev {dev.name} ingress")

    @property
    def dump_tc_rules_devices(self):
        return [dev for host in self.matched for dev in [host.eth0, host.sriov_devices.vf_reps[0]]]

    def generate_test_wide_description(self, config: EnrtConfiguration):
        desc = super().generate_test_wide_description(config)
        for host in [self.matched.host1, self.matched.host2]:
            desc += [
                f"Configured {host.hostid}.{host.eth0.name}.driver = switchdev\n"
                f"Created virtual function on {host.hostid}.{host.eth0.name} = {host.sriov_devices.vfs[0].name}\n"
                f"Created network_namespace on {host.hostid} = {host.newns.name}\n"
                f"Moved interface {host.sriov_devices.vfs[0].name} from {host.hostid} root namespace to {host.hostid}.{host.newns.name} namespace\n"
                f"Created tc rules for the connectivity between virtual functions\n"
            ]
        desc += [
            f"Configured {dev.host.hostid}.{dev.name}.ips = {dev.ips}"
            for dev in config.configured_devices
        ]
        return desc

    def test_wide_deconfiguration(self, config):
        """
        Test wide deconfiguration deletes all the virtual function devices,
        ingress filter rules and returns the control over the physical
        function to base driver.

        Derived classes need to provide a list of devices for which tc ingress
        qdisc was set previously through `config.ingress_devices` list.
        """
        for dev in config.ingress_devices:
            dev.host.run(f"tc qdisc del dev {dev.name} ingress")

        config.ingress_devices = []

        for host in [self.matched.host1, self.matched.host2]:
            host.eth0.delete_vfs()
            host.eth0.eswitch_mode = "legacy"
            del host.sriov_devices

        super().test_wide_deconfiguration(config)

    def generate_ping_endpoints(self, config):
        """
        The ping endpoints for this recipe are the virtual function devices

        host1.newns.vf_eth0 and host2.newns.vf_eth0
        """
        return [PingEndpoints(self.matched.host1.sriov_devices.vfs[0], self.matched.host2.sriov_devices.vfs[0])]

    def generate_perf_endpoints(self, config: EnrtConfiguration) -> list[Collection[EndpointPair[IPEndpoint]]]:
        """
        The perf endpoints for this recipe are the virtual function devices

        host1.newns.vf_eth0 and host2.newns.vf_eth0
        """
        return [ip_endpoint_pairs(config, (self.matched.host1.sriov_devices.vfs[0], self.matched.host2.sriov_devices.vfs[0]))]

    @property
    def pause_frames_dev_list(self):
        raise NotImplementedError()

    @property
    def offload_nics(self):
        raise NotImplementedError()

    @property
    def mtu_hw_config_dev_list(self):
        raise NotImplementedError()

    @property
    def dev_interrupt_hw_config_dev_list(self):
        raise NotImplementedError()

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        raise NotImplementedError()
