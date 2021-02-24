from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.LatencyEnrtRecipe import LatencyEnrtRecipe
from lnst.Common.Parameters import Param, IntParam, ListParam
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)

class ShortLivedConnectionsRecipe(CommonHWSubConfigMixin, LatencyEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    perf_tests = Param(default=("tcp_rr", "tcp_crr", "udp_rr"))
    ip_versions = Param(default=("ipv4",))
    perf_msg_sizes = ListParam(default=[1000, 5000, 7000, 10000, 12000])

    def test_wide_configuration(self):
        host1, host2 = self.matched.host1, self.matched.host2

        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = [host1.eth0, host2.eth0]

        net_addr = "192.168.101"
        for i, host in enumerate([host1, host2], 10):
            host.eth0.down()
            host.eth0.ip_add(ipaddress(net_addr + "." + str(i) + "/24"))
            host.eth0.up()

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
            ])
        ]
        return desc

    def test_wide_deconfiguration(self, config):
        del config.test_wide_devices

        super().test_wide_deconfiguration(config)

    def generate_perf_endpoints(self, config):
        return [(self.matched.host1.eth0, self.matched.host2.eth0)]

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
