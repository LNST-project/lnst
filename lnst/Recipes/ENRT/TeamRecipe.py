from lnst.Common.Parameters import Param, StrParam, BoolParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.PerfReversibleFlowMixin import (
    PerfReversibleFlowMixin)
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Devices import TeamDevice


class TeamRecipe(PerfReversibleFlowMixin, CommonHWSubConfigMixin, OffloadSubConfigMixin,
    BaseEnrtRecipe):
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
        return [
            PingEndpoints(self.matched.host1.team0, self.matched.host2.eth0),
            PingEndpoints(self.matched.host2.eth0, self.matched.host1.team0)
        ]

    def generate_perf_endpoints(self, config):
        return [(self.matched.host1.team0, self.matched.host2.eth0)]

    @property
    def offload_nics(self):
        return [self.matched.host1.team0, self.matched.host2.eth0]

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.team0, self.matched.host2.eth0]

    @property
    def coalescing_hw_config_dev_list(self):
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0]
