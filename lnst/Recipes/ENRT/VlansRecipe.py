from lnst.Common.Parameters import Param
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.Recipes.ENRT.PingMixins import VlanPingEvaluatorMixin
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Devices import VlanDevice

class VlansRecipe(VlanPingEvaluatorMixin,
    CommonHWSubConfigMixin, OffloadSubConfigMixin,
    BaseEnrtRecipe):
    """
    This recipe implements Enrt testing for a network scenario that looks
    as follows

    .. code-block:: none

                             .--------.
                    .--------+ switch +-------.
                    |        '--------'       |
                .---'--.                   .--'---.
        .-------| eth0 |------.    .-------| eth0 |------.
        |       '------'      |    |       '------'      |
        |      /   |    \     |    |      /   |    \     |
        | vlan0  vlan1  vlan2 |    | vlan0  vlan1  vlan2 |
        | id=10  id=20  id=30 |    | id=10  id=20  id=30 |
        |                     |    |                     |
        |        host1        |    |        host2        |
        '---------------------'    '---------------------'

    All sub configurations are included via Mixin classes.

    The actual test machinery is implemented in the :any:`BaseEnrtRecipe` class.
    """
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="off", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="on", gso="off", tso="off", tx="on", rx="on"),
        dict(gro="on", gso="on", tso="off", tx="off", rx="on"),
        dict(gro="on", gso="on", tso="on", tx="on", rx="off")))

    def test_wide_configuration(self):
        """
        Test wide configuration for this recipe involves creating three
        VLAN (802.1Q) tunnels on top of the matched host's NIC with vlan
        ids 10, 20, 30. The same tunnels are configured on the second host.

        An IPv4 and IPv6 address is configured on each tunnel endpoint.

        | host1.vlan0 = 192.168.10.1/24 and fc00:0:0:1::1/64
        | host1.vlan1 = 192.168.20.1/24 and fc00:0:0:2::1/64
        | host1.vlan2 = 192.168.30.1/24 and fc00:0:0:3::1/64

        | host2.vlan0 = 192.168.10.2/24 and fc00:0:0:1::2/64
        | host2.vlan1 = 192.168.20.2/24 and fc00:0:0:2::2/64
        | host2.vlan2 = 192.168.30.2/24 and fc00:0:0:3::2/64

        """
        host1, host2 = self.matched.host1, self.matched.host2

        host1.eth0.down()
        host2.eth0.down()

        host1.vlan0 = VlanDevice(realdev=host1.eth0, vlan_id=10)
        host1.vlan1 = VlanDevice(realdev=host1.eth0, vlan_id=20)
        host1.vlan2 = VlanDevice(realdev=host1.eth0, vlan_id=30)
        host2.vlan0 = VlanDevice(realdev=host2.eth0, vlan_id=10)
        host2.vlan1 = VlanDevice(realdev=host2.eth0, vlan_id=20)
        host2.vlan2 = VlanDevice(realdev=host2.eth0, vlan_id=30)

        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = []
        for host in [host1, host2]:
            configuration.test_wide_devices.extend([host.vlan0, host.vlan1,
                host.vlan2])

        net_addr = "192.168"
        net_addr6 = "fc00:0:0"

        for i, host in enumerate([host1, host2]):
            host.vlan0.ip_add(ipaddress(net_addr + '.10' + '.' + str(i+1) +
                "/24"))
            host.vlan0.ip_add(ipaddress(net_addr6 + ":1::" + str(i+1) +
                "/64"))
            host.vlan1.ip_add(ipaddress(net_addr + '.20' + '.' + str(i+1) +
                "/24"))
            host.vlan1.ip_add(ipaddress(net_addr6 + ":2::" + str(i+1) +
                "/64"))
            host.vlan2.ip_add(ipaddress(net_addr + '.30' + '.' + str(i+1) +
                "/24"))
            host.vlan2.ip_add(ipaddress(net_addr6 + ":3::" + str(i+1) +
                "/64"))
            for dev in [host.eth0, host.vlan0, host.vlan1, host.vlan2]:
                dev.up()

        self.wait_tentative_ips(configuration.test_wide_devices)

        return configuration

    def generate_test_wide_description(self, config):
        """
        Test wide description is extended with the configured VLAN tunnels
        and their IP addresses
        """
        host1, host2 = self.matched.host1, self.matched.host2
        desc = super().generate_test_wide_description(config)
        desc += [
            "\n".join([
                "Configured {}.{}.ips = {}".format(
                    dev.host.hostid, dev.name, dev.ips
                )
                for dev in config.test_wide_devices
            ]),
            "\n".join([
                "Configured {}.{}.vlan_id = {}".format(
                    dev.host.hostid, dev.name, dev.vlan_id
                )
                for dev in config.test_wide_devices
            ]),
            "\n".join([
                "Configured {}.{}.realdev = {}".format(
                    dev.host.hostid, dev.name,
                    '.'.join([dev.host.hostid, dev.realdev.name])
                )
                for dev in config.test_wide_devices
            ])
        ]
        return desc

    def test_wide_deconfiguration(self, config):
        ""  # overriding the parent docstring
        del config.test_wide_devices

        super().test_wide_deconfiguration(config)

    def generate_ping_endpoints(self, config):
        """
        The ping endpoints for this recipe are all combinations of the VLAN
        tunnel endpoints of the hosts. Depending on the VLAN id match of each
        tunnel endpoint combination the *reachable* flag is set.

        Returned as::

            # list of PingEndpoints with the following pattern
            [PingEndpoints(src, dst, reachable=(src.vlan_id == dst.vlan_id)), ...]
        """
        host1, host2 = self.matched.host1, self.matched.host2
        result = []
        for src in [host1.vlan0, host1.vlan1, host1.vlan2]:
            for dst in [host2.vlan0, host2.vlan1, host2.vlan2]:
                result += [PingEndpoints(src, dst,
                    reachable=(src.vlan_id == dst.vlan_id))]
        return result

    def generate_perf_endpoints(self, config):
        """
        The perf endpoints for this recipe are the VLAN tunnel endpoints with
        VLAN id 10:

        host1.vlan0 and host2.vlan0

        Returned as::

            [(self.matched.host1.vlan0, self.matched.host2.vlan0)]
        """
        return [(self.matched.host1.vlan0, self.matched.host2.vlan0)]

    @property
    def offload_nics(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def mtu_hw_config_dev_list(self):
        result = []
        for host in [self.matched.host1, self.matched.host2]:
            for dev in [host.eth0, host.vlan0, host.vlan1, host.vlan2]:
                result.append(dev)
        return result

    @property
    def coalescing_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
