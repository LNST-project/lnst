from itertools import permutations
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.Devices import BridgeDevice, VxlanDevice

class VxlanMulticastRecipe(CommonHWSubConfigMixin, BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))
    host1.tap0 = DeviceReq(label="to_guest1")

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    guest1 = HostReq()
    guest1.eth0 = DeviceReq(label="to_guest1")

    def test_wide_configuration(self):
        host1, host2, guest1 = (self.matched.host1, self.matched.host2,
            self.matched.guest1)

        for dev in [host1.eth0, host2.eth0, guest1.eth0, host1.tap0]:
            dev.down()

        net_addr = "192.168.0"
        vxlan_net_addr = "192.168.100"
        vxlan_net_addr6 = "fc00:0:0:0"
        #TODO: Enable usage of a proper address (like 239.1.1.1)
        vxlan_group_ip = "192.168.0.3"

        host1.br0 = BridgeDevice()
        host1.br0.slave_add(host1.eth0)
        host1.br0.slave_add(host1.tap0)

        for machine in [host1, guest1, host2]:
            machine.vxlan0 = VxlanDevice(vxlan_id=1, group=vxlan_group_ip)

        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = [host1.br0, host1.vxlan0,
            guest1.eth0, guest1.vxlan0, host2.eth0, host2.vxlan0]

        for i, (machine, dev) in enumerate([(host1, host1.br0),
            (guest1, guest1.eth0), (host2, host2.eth0)]):
            dev.ip_add(ipaddress(net_addr + "." + str(i+1) + "/24"))
            machine.vxlan0.realdev = dev
            machine.vxlan0.ip_add(ipaddress(vxlan_net_addr + "." + str(i+1)
                + "/24"))
            machine.vxlan0.ip_add(ipaddress(vxlan_net_addr6 + "::" +
                str(i+1) + "/64"))

        for dev in [host1.eth0, host2.eth0, guest1.eth0, host1.tap0,
                    host1.br0, host1.vxlan0, host2.vxlan0, guest1.vxlan0]:
            dev.up()

        self.wait_tentative_ips(configuration.test_wide_devices)

        return configuration

    def generate_test_wide_description(self, config):
        host1, host2, guest1 = (self.matched.host1, self.matched.host2,
            self.matched.guest1)
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
                for dev in [host1.vxlan0, host2.vxlan0, guest1.vxlan0]
            ]),
            "\n".join([
                "Configured {}.{}.group = {}".format(
                    dev.host.hostid, dev.name, dev.group
                )
                for dev in [host1.vxlan0, host2.vxlan0, guest1.vxlan0]
            ]),
            "\n".join([
                "Configured {}.{}.realdev = {}".format(
                    dev.host.hostid, dev.name,
                    '.'.join([dev.host.hostid, dev.realdev.name])
                )
                for dev in [host1.vxlan0, host2.vxlan0, guest1.vxlan0]
            ])
        ]
        return desc

    def test_wide_deconfiguration(self, config):
        del config.test_wide_devices

        super().test_wide_deconfiguration(config)

    def generate_ping_endpoints(self, config):
        host1, host2, guest1 = (self.matched.host1, self.matched.host2,
            self.matched.guest1)
        devs = [host1.vxlan0, host2.vxlan0, guest1.vxlan0]
        return permutations(devs,2)

    def generate_perf_endpoints(self, config):
        host1, host2, guest1 = (self.matched.host1, self.matched.host2,
            self.matched.guest1)
        return [(self.matched.host1.vxlan0, self.matched.host2.vxlan0)]

    def wait_tentative_ips(self, devices):
        def condition():
            return all(
                [not ip.is_tentative for dev in devices for ip in dev.ips]
            )

        self.ctl.wait_for_condition(condition, timeout=5)

    @property
    def mtu_hw_config_dev_list(self):
        host1, host2, guest1 = (self.matched.host1, self.matched.host2,
            self.matched.guest1)
        return [host1.vxlan0, host2.vxlan0, guest1.vxlan0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        host1, host2 = (self.matched.host1, self.matched.host2)
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        host1, host2 = (self.matched.host1, self.matched.host2)
        return [self.matched.host1.eth0, self.matched.host2.eth0]
