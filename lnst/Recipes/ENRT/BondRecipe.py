from lnst.Common.Parameters import (
    Param,
    IntParam,
    StrParam,
    IPv4NetworkParam,
    IPv6NetworkParam,
)
from lnst.Common.IpAddress import interface_addresses
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaremetalEnrtRecipe import BaremetalEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.PerfReversibleFlowMixin import (
    PerfReversibleFlowMixin)
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Devices import BondDevice

class BondRecipe(PerfReversibleFlowMixin, CommonHWSubConfigMixin, OffloadSubConfigMixin,
    BaremetalEnrtRecipe):
    """
    This recipe implements Enrt testing for a network scenario that looks
    as follows

    .. code-block:: none

                                    .--------.
                   .----------------+        |
                   |        .-------+ switch +-------.
                   |        |       '--------'       |
             .-------------------.                   |
             |     | bond0  |    |                   |
             | .---'--. .---'--. |               .---'--.
        .----|-| eth0 |-| eth1 |-|----.     .----| eth0 |----.
        |    | '------' '------' |    |     |    '------'    |
        |    '-------------------'    |     |                |
        |                             |     |                |
        |            host1            |     |      host2     |
        '-----------------------------'     '----------------'

    The recipe provides additional recipe parameters to configure the bonding
    device.

        :param bonding_mode:
            (mandatory test parameter) the bonding mode to be configured on
            the bond0 device.
        :param miimon_value:
            (mandatory test parameter) the miimon interval to be configured
            on the bond0 device.

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

    net_ipv4 = IPv4NetworkParam(default="192.168.101.0/24")
    net_ipv6 = IPv6NetworkParam(default="fc00::/64")

    bonding_mode = StrParam(mandatory=True)
    miimon_value = IntParam(mandatory=True)

    def test_wide_configuration(self):
        """
        Test wide configuration for this recipe involves creating a bonding
        device using the two matched physical devices as slaves on host1.
        The bonding mode and miimon interval is configured on the bonding device
        according to the recipe parameters. IPv4 and IPv6 addresses are added to
        the bonding device and to the matched ethernet device on host2.

        | host1.bond0 = 192.168.101.1/24 and fc00::1/64
        | host2.eth0 = 192.168.101.2/24 and fc00::2/64
        """

        host1, host2 = self.matched.host1, self.matched.host2
        host1.bond0 = BondDevice(mode=self.params.bonding_mode,
            miimon=self.params.miimon_value)
        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = []

        for dev in [host1.eth0, host1.eth1]:
            dev.down()
            host1.bond0.slave_add(dev)

        ipv4_addr = interface_addresses(self.params.net_ipv4)
        ipv6_addr = interface_addresses(self.params.net_ipv6)

        for i, dev in enumerate([host1.bond0, host2.eth0]):
            dev.ip_add(next(ipv4_addr))
            dev.ip_add(next(ipv6_addr))
            configuration.test_wide_devices.append(dev)

        for dev in [host1.eth0, host1.eth1, host1.bond0, host2.eth0]:
            dev.up()

        self.wait_tentative_ips(configuration.test_wide_devices)

        return configuration

    def generate_test_wide_description(self, config):
        """
        Test wide description is extended with the configured IP addresses, the
        configured bonding slave interfaces, bonding mode and the miimon interval.
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
        The ping endpoints for this recipe are the configured bonding device on
        host1 and the matched ethernet device on host2.

        Returned as::

            [PingEndpoints(self.matched.host1.bond0, self.matched.host2.eth0)
        """
        return [PingEndpoints(self.matched.host1.bond0, self.matched.host2.eth0)]

    def generate_perf_endpoints(self, config):
        """
        The perf endpoints for this recipe are the configured bonding device on
        host1 and the matched ethernet device on host2. The traffic egresses
        the bonding device.

        | host1.bond0
        | host2.eth0

        Returned as::

            [(self.matched.host1.bond0, self.matched.host2.eth0)]

        """
        return [(self.matched.host1.bond0, self.matched.host2.eth0)]

    @property
    def offload_nics(self):
        """
        The `offload_nics` property value for this scenario is a list containing
        the configured bonding device on host1 and the matched ethernet device
        on host2.

        | host1.bond0
        | host2.eth0

        For detailed explanation of this property see :any:`OffloadSubConfigMixin`
        class and :any:`OffloadSubConfigMixin.offload_nics`.
        """
        return [self.matched.host1.bond0, self.matched.host2.eth0]

    @property
    def mtu_hw_config_dev_list(self):
        """
        The `mtu_hw_config_dev_list` property value for this scenario is a list
        containing the configured bonding device on host1 and the matched ethernet
        device on host2.

        | host1.bond0
        | host2.eth0

        For detailed explanation of this property see :any:`MTUHWConfigMixin`
        class and :any:`MTUHWConfigMixin.mtu_hw_config_dev_list`.
        """
        return [self.matched.host1.bond0, self.matched.host2.eth0]

    @property
    def coalescing_hw_config_dev_list(self):
        """
        The `coalescing_hw_config_dev_list` property value for this scenario is a
        list containing the matched physical devices used to create the bonding
        device on host1 and the matched ethernet device on host2.

        | host1.eth0, host.eth1
        | host2.eth0

        For detailed explanation of this property see :any:`CoalescingHWConfigMixin`
        class and :any:`CoalescingHWConfigMixin.coalescing_hw_config_dev_list`.
        """
        return [self.matched.host1.eth0, self.matched.host1.eth1,
            self.matched.host2.eth0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        """
        The `dev_interrupt_hw_config_dev_list` property value for this scenario
        is a list containing the matched physical devices used to create the
        bonding device on host1 and the matched ethernet device on host2.

        | host1.eth0, host1.eth1
        | host2.eth0

        For detailed explanation of this property see
        :any:`DevInterruptHWConfigMixin` class and
        :any:`CoalescingHWConfigMixin.coalescing_hw_config_dev_list`.
        """
        return [self.matched.host1.eth0, self.matched.host1.eth1,
            self.matched.host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        """
        The `parallel_stream_qdisc_hw_config_dev_list` property value for this
        scenario is a list containing the matched physical devices used to create
        the bonding device on host1 and the matched ethernet device on host2.

        | host1.eth0, host.eth1
        | host2.eth0

        For detailed explanation of this property see
        :any:`ParallelStreamQDiscHWConfigMixin` class and
        :any:`ParallelStreamQDiscHWConfigMixin.parallel_stream_qdisc_hw_config_dev_list`.
        """
        return [self.matched.host1.eth0, self.matched.host1.eth1,
            self.matched.host2.eth0]

    @property
    def pause_frames_dev_list(self):
        """
        The `pause_frames_dev_list` property value for this scenario is a list
        containing the matched physical devices used to create the bonding
        device on host1 and the matched ethernet device on host2.

        | host1.eth0, host.eth1
        | host2.eth0

        For detailed explanation of this property see
        :any:`PauseFramesHWConfigMixin` and
        :any:`PauseFramesHWConfigMixin.pause_frames_dev_list`.
        """
        return [self.matched.host1.eth0, self.matched.host1.eth1,
            self.matched.host2.eth0]
