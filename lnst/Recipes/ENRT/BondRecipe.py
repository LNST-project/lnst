from lnst.Common.Parameters import Param, IntParam, StrParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Devices import BondDevice

class BondRecipe(CommonHWSubConfigMixin, OffloadSubConfigMixin,
    BaseEnrtRecipe):
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
        host1, host2 = self.matched.host1, self.matched.host2
        host1.bond0 = BondDevice(mode=self.params.bonding_mode,
            miimon=self.params.miimon_value)
        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = []

        for dev in [host1.eth0, host1.eth1]:
            dev.down()
            host1.bond0.slave_add(dev)

        net_addr = "192.168.101"
        net_addr6 = "fc00:0:0:0"
        for i, dev in enumerate([host1.bond0, host2.eth0]):
            dev.ip_add(ipaddress(net_addr + "." + str(i+1) + "/24"))
            dev.ip_add(ipaddress(net_addr6 + "::" + str(i+1) + "/64"))
            configuration.test_wide_devices.append(dev)

        for dev in [host1.eth0, host1.eth1, host1.bond0, host2.eth0]:
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
        return [PingEndpoints(self.matched.host1.bond0, self.matched.host2.eth0)]

    def generate_perf_endpoints(self, config):
        return [(self.matched.host1.bond0, self.matched.host2.eth0)]

    @property
    def offload_nics(self):
        return [self.matched.host1.bond0, self.matched.host2.eth0]

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.bond0, self.matched.host2.eth0]

    @property
    def coalescing_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host1.eth1,
            self.matched.host2.eth0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host1.eth1,
            self.matched.host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host1.eth1,
            self.matched.host2.eth0]

    @property
    def no_pause_frames_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host1.eth1,
                self.matched.host2.eth0]
