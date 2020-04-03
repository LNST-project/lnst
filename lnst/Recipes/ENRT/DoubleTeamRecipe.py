from lnst.Common.Parameters import Param, StrParam, BoolParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Devices import TeamDevice

class DoubleTeamRecipe(CommonHWSubConfigMixin, OffloadSubConfigMixin,
    BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="tnet", driver=RecipeParam("driver"))
    host1.eth1 = DeviceReq(label="tnet", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="tnet", driver=RecipeParam("driver"))
    host2.eth1 = DeviceReq(label="tnet", driver=RecipeParam("driver"))

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on"),
        dict(gro="off", gso="on", tso="on", tx="on"),
        dict(gro="on", gso="off", tso="off", tx="on"),
        dict(gro="on", gso="on", tso="off", tx="off")))

    perf_reverse = BoolParam(default=True)
    runner_name = StrParam(mandatory=True)

    def test_wide_configuration(self):
        host1, host2 = self.matched.host1, self.matched.host2

        net_addr_1 = "192.168.10"
        net_addr6_1 = "fc00:0:0:1"
        for i, host in enumerate([host1, host2]):
            #The config argument needs to be used with a team device
            #normally (e.g  to specify the runner mode), but it is not used
            #here due to a bug in the TeamDevice module
            host.team0 = TeamDevice()
            for dev in [host.eth0, host.eth1]:
                dev.down()
                host.team0.slave_add(dev)
            host.team0.ip_add(ipaddress(net_addr_1 + "." + str(i+1) +
                "/24"))
            host.team0.ip_add(ipaddress(net_addr6_1 + "::" + str(i+1) +
                "/64"))
            for dev in [host.eth0, host.eth1, host.team0]:
                dev.up()

        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = [host1.team0, host2.team0]

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
            "\n".join([
                "Configured {}.{}.slaves = {}".format(
                    dev.host.hostid, dev.name,
                    ['.'.join([dev.host.hostid, slave.name])
                    for slave in dev.slaves]
                )
                for dev in config.test_wide_devices
            ]),
            "\n".join([
                "Configured {}.{}.runner_name = {}".format(
                    dev.host.hostid, dev.name, dev.config
                )
                for dev in config.test_wide_devices
            ])
        ]
        return desc

    def test_wide_deconfiguration(self, config):
        del config.test_wide_devices

        super().test_wide_deconfiguration(config)

    def generate_ping_endpoints(self, config):
        return [
            PingEndpoints(self.matched.host1.team0, self.matched.host2.team0),
            PingEndpoints(self.matched.host2.team0, self.matched.host1.team0)
        ]

    def generate_perf_endpoints(self, config):
        return [(self.matched.host1.team0, self.matched.host2.team0),
            (self.matched.host2.team0, self.matched.host1.team0)]

    @property
    def offload_nics(self):
        return [self.matched.host1.team0, self.matched.host2.team0]

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.team0, self.matched.host2.team0]

    @property
    def coalescing_hw_config_dev_list(self):
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0, host2.eth1]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0, host2.eth1]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0, host2.eth1]
