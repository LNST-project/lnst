from lnst.Common.Parameters import Param, StrParam, BoolParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaremetalEnrtRecipe import BaremetalEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.PerfReversibleFlowMixin import (
    PerfReversibleFlowMixin)
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Devices import TeamDevice


class TeamRecipe(PerfReversibleFlowMixin, CommonHWSubConfigMixin, OffloadSubConfigMixin,
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
             |     | team0  |    |                   |
             | .---'--. .---'--. |               .---'--.
        .----|-| eth0 |-| eth1 |-|----.     .----| eth0 |----.
        |    | '------' '------' |    |     |    '------'    |
        |    '-------------------'    |     |                |
        |                             |     |                |
        |            host1            |     |      host2     |
        '-----------------------------'     '----------------'


    The recipe provides additional recipe parameters to configure the teaming
    device.

        :param runner_name:
            (mandatory test parameter) the teamd runner to be use on
            the team0 device (ex. `activebackup`, `roundrobin`, etc)

    All sub configurations are included via Mixin classes.

    The actual test machinery is implemented in the :any:`BaseEnrtRecipe` class.
    """
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="tnet", driver=RecipeParam("driver"))
    host1.eth1 = DeviceReq(label="tnet", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="tnet", driver=RecipeParam("driver"))

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on"),
        dict(gro="off", gso="on", tso="on", tx="on"),
        dict(gro="on", gso="off", tso="off", tx="on"),
        dict(gro="on", gso="on", tso="off", tx="off")))

    runner_name = StrParam(mandatory=True)

    def test_wide_configuration(self):
        """
        Test wide configuration for this recipe involves creating a team
        device using the two matched physical devices as ports on host1.
        The `teamd` daemon is configured with the `runner_name` according
        to the recipe parameters. IPv4 and IPv6 addresses are added to
        the teaming device and to the matched ethernet device on host2.

        | host1.team0 = 192.168.10.1/24 and fc00:0:0:1::1/64
        | host2.eth0 = 192.168.10.2/24 and fc00:0:0:1::2/64
        """
        host1, host2 = self.matched.host1, self.matched.host2

        teamd_config = {'runner': {'name': self.params.runner_name}}
        host1.team0 = TeamDevice(config=teamd_config)

        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = [host1.team0, host2.eth0]

        for dev in [host1.eth0, host1.eth1]:
            dev.down()
            host1.team0.slave_add(dev)

        net_addr_1 = "192.168.10"
        net_addr6_1 = "fc00:0:0:1"
        for i, dev in enumerate([host1.team0, host2.eth0]):
            dev.ip_add(ipaddress(net_addr_1 + "." + str(i+1) + "/24"))
            dev.ip_add(ipaddress(net_addr6_1 + "::" + str(i+1) + "/64"))

        for dev in [host1.eth0, host1.eth1, host1.team0, host2.eth0]:
            dev.up()

        self.wait_tentative_ips(configuration.test_wide_devices)

        return configuration

    def generate_test_wide_description(self, config):
        """
        Test wide description is extended with the configured IP addresses, the
        configured team device ports, and runner name.
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
                host1.hostid, host1.team0.name,
                ['.'.join([host1.hostid, slave.name])
                for slave in host1.team0.slaves]
            ),
            "Configured {}.{}.runner_name = {}".format(
                host1.hostid, host1.team0.name,
                host1.team0.config
            )
        ]
        return desc

    def test_wide_deconfiguration(self, config):
        del config.test_wide_devices

        super().test_wide_deconfiguration(config)

    def generate_ping_endpoints(self, config):
        """
        The ping endpoints for this recipe are the configured team device on
        host1 and the matched ethernet device on host2.

        Returned as::

            [PingEndpoints(self.matched.host1.team0, self.matched.host2.eth0),
            PingEndpoints(self.matched.host2.eth0, self.matched.host1.team0)]
        """
        return [
            PingEndpoints(self.matched.host1.team0, self.matched.host2.eth0),
            PingEndpoints(self.matched.host2.eth0, self.matched.host1.team0)
        ]

    def generate_perf_endpoints(self, config):
        """
        The perf endpoints for this recipe are the configured team device on
        host1 and the matched ethernet device on host2. The traffic egresses
        the team device.

        | host1.team0
        | host2.eth0

        Returned as::

            [(self.matched.host1.team0, self.matched.host2.eth0)]

        """
        return [(self.matched.host1.team0, self.matched.host2.eth0)]

    @property
    def offload_nics(self):
        """
        The `offload_nics` property value for this scenario is a list containing
        the configured team device on host1 and the matched ethernet device
        on host2.

        | host1.team0
        | host2.eth0

        For detailed explanation of this property see :any:`OffloadSubConfigMixin`
        class and :any:`OffloadSubConfigMixin.offload_nics`.
        """
        return [self.matched.host1.team0, self.matched.host2.eth0]

    @property
    def mtu_hw_config_dev_list(self):
        """
        The `mtu_hw_config_dev_list` property value for this scenario is a list
        containing the configured teaming device on host1 and the matched ethernet
        device on host2.

        | host1.team0
        | host2.eth0

        For detailed explanation of this property see :any:`MTUHWConfigMixin`
        class and :any:`MTUHWConfigMixin.mtu_hw_config_dev_list`.
        """
        return [self.matched.host1.team0, self.matched.host2.eth0]

    @property
    def coalescing_hw_config_dev_list(self):
        """
        The `coalescing_hw_config_dev_list` property value for this scenario is a
        list containing the matched physical devices used to create the teaming
        device on host1 and the matched ethernet device on host2.

        | host1.eth0, host.eth1
        | host2.eth0

        For detailed explanation of this property see :any:`CoalescingHWConfigMixin`
        class and :any:`CoalescingHWConfigMixin.coalescing_hw_config_dev_list`.
        """
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        """
        The `dev_interrupt_hw_config_dev_list` property value for this scenario
        is a list containing the matched physical devices used to create the
        teaming device on host1 and the matched ethernet device on host2.

        | host1.eth0, host1.eth1
        | host2.eth0

        For detailed explanation of this property see
        :any:`DevInterruptHWConfigMixin` class and
        :any:`DevInterruptHWConfigMixin.dev_interrupt_hw_config_dev_list`.
        """
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        """
        The `parallel_stream_qdisc_hw_config_dev_list` property value for this
        scenario is a list containing the matched physical devices used to create
        the teaming device on host1 and the matched ethernet device on host2.

        | host1.eth0, host.eth1
        | host2.eth0

        For detailed explanation of this property see
        :any:`ParallelStreamQDiscHWConfigMixin` class and
        :any:`ParallelStreamQDiscHWConfigMixin.parallel_stream_qdisc_hw_config_dev_list`.
        """
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0]
