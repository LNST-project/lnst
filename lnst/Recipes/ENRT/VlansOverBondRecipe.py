from lnst.Common.Parameters import Param, IntParam, StrParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaremetalEnrtRecipe import BaremetalEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.PerfReversibleFlowMixin import (
    PerfReversibleFlowMixin)
from lnst.Devices import VlanDevice
from lnst.Devices.VlanDevice import VlanDevice as Vlan
from lnst.Devices import BondDevice
from lnst.Recipes.ENRT.PingMixins import VlanPingEvaluatorMixin
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints

class VlansOverBondRecipe(PerfReversibleFlowMixin, VlanPingEvaluatorMixin,
    CommonHWSubConfigMixin, OffloadSubConfigMixin,
    BaremetalEnrtRecipe):
    """
    This recipe implements Enrt testing for a network scenario that looks
    as follows

    .. code-block:: none

                              .--------.
                .-------------+ switch +--------.
                |         .---+        |        |
                |         |   '--------'        |
          .-----|---------|----.                |
          | .---'--.  .---'--. |             .--'---.
        .-|-| eth0 |--| eth1 |-|-.   .-------| eth0 |------.
        | | '------'  '------' | |   |       '------'      |
        | |        bond0       | |   |      /   |    \     |
        | '-------/--|--\------' |   | vlan0  vlan1  vlan2 |
        |        /   |   \       |   | id=10  id=20  id=30 |
        |   vlan0  vlan1  vlan2  |   |                     |
        |   id=10  id=20  id=30  |   |                     |
        |                        |   |                     |
        |          host1         |   |        host2        |
        '------------------------'   '---------------------'

    The recipe provides additional recipe parameters to configure the bonding
    device.

    :param bonding_mode:
        (mandatory test parameter) the bonding mode to be configured on
        the bond0 device
    :param miimon_value:
        (mandatory test parameter) the miimon interval to be configured
        on the bond0 device

    All sub configurations are included via Mixin classes.

    The actual test machinery is implemented in the :any:`BaseEnrtRecipe` class.
    """
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))
    host1.eth1 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on"),
        dict(gro="off", gso="on", tso="on", tx="on"),
        dict(gro="on", gso="off", tso="off", tx="on"),
        dict(gro="on", gso="on", tso="off", tx="off")))

    bonding_mode = StrParam(mandatory=True)
    miimon_value = IntParam(mandatory=True)

    def test_wide_configuration(self):
        """
        Test wide configuration for this recipe involves creating one bonding
        device on the first host. This device bonds two NICs matched by the
        recipe. The bonding mode and miimon interval is configured on the
        bonding device according to the recipe parameters. Then three
        VLAN (802.1Q) tunnels are created on top of the bonding device on the
        first host and on the matched NIC on the second host. The tunnels are
        configured with ids 10, 20, 30.

        An IPv4 and IPv6 address is configured on each tunnel endpoint.

        | host1.vlan0 = 192.168.10.1/24 and fc00:0:0:1::1/64
        | host1.vlan1 = 192.168.20.1/24 and fc00:0:0:2::1/64
        | host1.vlan2 = 192.168.30.1/24 and fc00:0:0:3::1/64

        | host2.vlan0 = 192.168.10.2/24 and fc00:0:0:1::2/64
        | host2.vlan1 = 192.168.20.2/24 and fc00:0:0:2::2/64
        | host2.vlan2 = 192.168.30.2/24 and fc00:0:0:3::2/64
        """
        host1, host2 = self.matched.host1, self.matched.host2

        host1.bond0 = BondDevice(mode=self.params.bonding_mode,
            miimon=self.params.miimon_value)
        for dev in [host1.eth0, host1.eth1]:
            dev.down()
            host1.bond0.slave_add(dev)

        host1.vlan0 = VlanDevice(realdev=host1.bond0, vlan_id=10)
        host1.vlan1 = VlanDevice(realdev=host1.bond0, vlan_id=20)
        host1.vlan2 = VlanDevice(realdev=host1.bond0, vlan_id=30)
        host2.vlan0 = VlanDevice(realdev=host2.eth0, vlan_id=10)
        host2.vlan1 = VlanDevice(realdev=host2.eth0, vlan_id=20)
        host2.vlan2 = VlanDevice(realdev=host2.eth0, vlan_id=30)

        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = []
        for host in [host1, host2]:
            configuration.test_wide_devices.extend([host.vlan0,
                host.vlan1, host.vlan2])
        configuration.test_wide_devices.append(host1.bond0)

        net_addr = "192.168"
        net_addr6 = "fc00:0:0"

        for i, host in enumerate([host1, host2]):
            host.vlan0.ip_add(ipaddress('{}.10.{}/24'.format(net_addr, i+1)))
            host.vlan1.ip_add(ipaddress('{}.20.{}/24'.format(net_addr, i+1)))
            host.vlan2.ip_add(ipaddress('{}.30.{}/24'.format(net_addr, i+1)))
            host.vlan0.ip_add(ipaddress('{}:1::{}/64'.format(net_addr6, i+1)))
            host.vlan1.ip_add(ipaddress('{}:2::{}/64'.format(net_addr6, i+1)))
            host.vlan2.ip_add(ipaddress('{}:3::{}/64'.format(net_addr6, i+1)))

        for dev in [host1.eth0, host1.eth1, host1.bond0, host1.vlan0,
            host1.vlan1, host1.vlan2, host2.eth0, host2.vlan0,
            host2.vlan1, host2.vlan2]:
            dev.up()

        self.wait_tentative_ips(configuration.test_wide_devices)

        return configuration

    def generate_test_wide_description(self, config):
        """
        Test wide description is extended with the configured VLAN tunnels,
        their IP addresses and the bonding device configuration.
        """
        host1, host2 = self.matched.host1, self.matched.host2
        desc = super().generate_test_wide_description(config)
        desc += [
            "\n".join([
                "Configured {}.{}.ips = {}".format(
                    dev.host.hostid, dev.name, dev.ips
                )
                for dev in config.test_wide_devices if isinstance(dev,
                    Vlan)
            ]),
            "\n".join([
                "Configured {}.{}.vlan_id = {}".format(
                    dev.host.hostid, dev.name, dev.vlan_id
                )
                for dev in config.test_wide_devices if isinstance(dev,
                    Vlan)
            ]),
            "\n".join([
                "Configured {}.{}.realdev = {}".format(
                    dev.host.hostid, dev.name,
                    '.'.join([dev.host.hostid, dev.realdev.name])
                )
                for dev in config.test_wide_devices if isinstance(dev,
                    Vlan)
            ]),
            "Configured {}.{}.slaves = {}".format(
                host1.hostid, host1.bond0.name,
                ['.'.join([host1.hostid, slave.name])
                for slave in host1.bond0.slaves]
            ),
            "Configured {}.{}.mode = {}".format(
                host1.hostid, host1.bond0.name,
                host1.bond0.mode
            ),
            "Configured {}.{}.miimon = {}".format(
                host1.hostid, host1.bond0.name,
                host1.bond0.miimon
            )
        ]
        return desc

    def test_wide_deconfiguration(self, config):
        del config.test_wide_devices

        super().test_wide_deconfiguration(config)

    def generate_ping_endpoints(self, config):
        """
        The ping endpoints for this recipe are the matching VLAN tunnel
        endpoints of the hosts.

        Returned as::

            [PingEndpoints(host1.vlan0, host2.vlan0),
             PingEndpoints(host1.vlan1, host2.vlan1),
             PingEndpoints(host1.vlan2, host2.vlan2)]
        """
        host1, host2 = self.matched.host1, self.matched.host2

        return [PingEndpoints(host1.vlan0, host2.vlan0),
                PingEndpoints(host1.vlan1, host2.vlan1),
                PingEndpoints(host1.vlan2, host2.vlan2)]

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
        """
        The `offload_nics` property value for this scenario is a list of the
        physical devices carrying data of the configured VLAN tunnels:

        host1.eth0, host1.eth1 and host2.eth0

        For detailed explanation of this property see :any:`OffloadSubConfigMixin`
        class and :any:`OffloadSubConfigMixin.offload_nics`.
        """
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0]

    @property
    def mtu_hw_config_dev_list(self):
        """
        The `mtu_hw_config_dev_list` property value for this scenario is a
        list of all configured VLAN tunnel devices and the underlying bonding
        or physical devices:

        | host1.bond0, host1.vlan0, host1.vlan1, host1.vlan2
        | host2.eth0, host2.vlan0, host2.vlan1, host2.vlan2

        For detailed explanation of this property see :any:`MTUHWConfigMixin`
        class and :any:`MTUHWConfigMixin.mtu_hw_config_dev_list`.
        """
        host1, host2 = self.matched.host1, self.matched.host2
        result = []
        for host in [host1, host2]:
            for dev in [host.vlan0, host.vlan1, host.vlan2]:
                result.append(dev)
        result.extend([host1.bond0, host2.eth0])
        return result

    @property
    def coalescing_hw_config_dev_list(self):
        """
        The `coalescing_hw_config_dev_list` property value for this scenario
        is a list of the physical devices carrying data of the configured
        VLAN tunnels:

        host1.eth0, host1.eth1 and host2.eth0

        For detailed explanation of this property see :any:`CoalescingHWConfigMixin`
        class and :any:`CoalescingHWConfigMixin.coalescing_hw_config_dev_list`.
        """
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        """
        The `dev_interrupt_hw_config_dev_list` property value for this scenario
        is a list of the physical devices carrying data of the configured
        VLAN tunnels:

        host1.eth0, host1.eth1 and host2.eth0

        For detailed explanation of this property see :any:`DevInterruptHWConfigMixin`
        class and :any:`DevInterruptHWConfigMixin.dev_interrupt_hw_config_dev_list`.
        """
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        """
        The `parallel_stream_qdisc_hw_config_dev_list` property value for
        this scenario is a list of the physical devices carrying data of the
        configured VLAN tunnels:

        host1.eth0, host1.eth1 and host2.eth0

        For detailed explanation of this property see
        :any:`ParallelStreamQDiscHWConfigMixin` class and
        :any:`ParallelStreamQDiscHWConfigMixin.parallel_stream_qdisc_hw_config_dev_list`.
        """
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0]

    @property
    def pause_frames_dev_list(self):
        """
        The `pause_frames_dev_list` property value for this scenario is a list
        of the physical devices carrying data of the configured VLAN tunnels:

        host1.eth0, host1.eth1 and host2.eth0

        For detailed explanation of this property see
        :any:`PauseFramesHWConfigMixin` and
        :any:`PauseFramesHWConfigMixin.pause_frames_dev_list`.
        """
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0]
