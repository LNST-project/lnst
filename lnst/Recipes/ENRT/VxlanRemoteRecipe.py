from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaremetalEnrtRecipe import BaremetalEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Devices import VxlanDevice

class VxlanRemoteRecipe(CommonHWSubConfigMixin, BaremetalEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    def test_wide_configuration(self):
        host1, host2 = self.matched.host1, self.matched.host2

        for host in [host1, host2]:
            host.eth0.down()

        net_addr = "192.168.0"
        vxlan_net_addr = "192.168.100"
        vxlan_net_addr6 = "fc00:0:0:0"

        for i, host in enumerate([host1, host2]):
            host.eth0.ip_add(ipaddress(net_addr + "." + str(i+1) + "/24"))
            host.vxlan0 = VxlanDevice(vxlan_id='1', remote=net_addr +
                "." + str(2-i))

        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = [host1.eth0, host1.vxlan0,
            host2.eth0, host2.vxlan0]

        for i, host in enumerate([host1, host2]):
            host.vxlan0.realdev = host.eth0
            host.vxlan0.ip_add(ipaddress(vxlan_net_addr + "." + str(i+1) +
                "/24"))
            host.vxlan0.ip_add(ipaddress(vxlan_net_addr6 + "::" + str(i+1)
                + "/64"))

        for host in [host1, host2]:
            host.eth0.up()
            host.vxlan0.up()

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
                "Configured {}.{}.vxlan_id = {}".format(
                    dev.host.hostid, dev.name, dev.vxlan_id
                )
                for dev in [host1.vxlan0, host2.vxlan0]
            ]),
            "\n".join([
                "Configured {}.{}.remote = {}".format(
                    dev.host.hostid, dev.name, dev.remote
                )
                for dev in [host1.vxlan0, host2.vxlan0]
            ]),
            "\n".join([
                "Configured {}.{}.realdev = {}".format(
                    dev.host.hostid, dev.name,
                    '.'.join([dev.host.hostid, dev.realdev.name])
                )
                for dev in [host1.vxlan0, host2.vxlan0]
            ])
        ]
        return desc

    def test_wide_deconfiguration(self, config):
        del config.test_wide_devices

        super().test_wide_deconfiguration(config)

    def generate_ping_endpoints(self, config):
        return [PingEndpoints(self.matched.host1.vxlan0, self.matched.host2.vxlan0)]

    def generate_perf_endpoints(self, config):
        return [(self.matched.host1.vxlan0, self.matched.host2.vxlan0)]

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.vxlan0, self.matched.host2.vxlan0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
