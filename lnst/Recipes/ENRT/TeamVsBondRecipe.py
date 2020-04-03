from lnst.Common.Parameters import Param, IntParam, StrParam, BoolParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Devices import TeamDevice
from lnst.Devices import BondDevice

class TeamVsBondRecipe(CommonHWSubConfigMixin, OffloadSubConfigMixin,
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
    runner_name = StrParam(mandatory = True)
    bonding_mode = StrParam(mandatory = True)
    miimon_value = IntParam(mandatory = True)

    def test_wide_configuration(self):
        host1, host2 = self.matched.host1, self.matched.host2

        #The config argument needs to be used with a team device normally
        #(e.g  to specify the runner mode), but it is not used here due to
        #a bug in the TeamDevice module
        host1.team0 = TeamDevice()

        host2.bond0 = BondDevice(mode=self.params.bonding_mode,
            miimon=self.params.miimon_value)

        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = [host1.team0, host2.bond0]

        net_addr_1 = "192.168.10"
        net_addr6_1 = "fc00:0:0:1"

        for i, (host, dev) in enumerate([(host1, host1.team0), (host2,
            host2.bond0)]):
            host.eth0.down()
            host.eth1.down()
            dev.slave_add(host.eth0)
            dev.slave_add(host.eth1)
            dev.ip_add(ipaddress(net_addr_1 + "." + str(i+1) + "/24"))
            dev.ip_add(ipaddress(net_addr6_1 + "::" + str(i+1) + "/64"))

        for host, dev in [(host1, host1.team0), (host2, host2.bond0)]:
            host.eth0.up()
            host.eth1.up()
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
            "\n".join([
                "Configured {}.{}.slaves = {}".format(
                    dev.host.hostid, dev.name,
                    ['.'.join([dev.host.hostid, slave.name])
                    for slave in dev.slaves]
                )
                for dev in config.test_wide_devices
            ]),
            "Configured {}.{}.runner_name = {}".format(
                host1.hostid, host1.team0.name,
                host1.team0.config
            ),
            "Configured {}.{}.mode = {}".format(
                host2.hostid, host2.bond0.name,
                host2.bond0.mode
            ),
            "Configured {}.{}.miimon = {}".format(
                host2.hostid, host2.bond0.name,
                host2.bond0.miimon
            )
        ]
        return desc

    def test_wide_deconfiguration(self, config):
        del config.test_wide_devices

        super().test_wide_deconfiguration(config)

    def generate_ping_endpoints(self, config):
        return [
            PingEndpoints(self.matched.host1.team0, self.matched.host2.bond0),
            PingEndpoints(self.matched.host2.bond0, self.matched.host1.team0)
        ]

    def generate_perf_endpoints(self, config):
        return [(self.matched.host1.team0, self.matched.host2.bond0),
            (self.matched.host2.bond0, self.matched.host1.team0)]

    @property
    def offload_nics(self):
        return [self.matched.host1.team0, self.matched.host2.bond0]

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.team0, self.matched.host2.bond0]

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
