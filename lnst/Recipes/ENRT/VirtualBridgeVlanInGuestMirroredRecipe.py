import logging
from lnst.Common.Parameters import Param
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.VirtualEnrtRecipe import VirtualEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Devices import VlanDevice
from lnst.Devices import BridgeDevice

class VirtualBridgeVlanInGuestMirroredRecipe(CommonHWSubConfigMixin,
    OffloadSubConfigMixin, VirtualEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))
    host1.tap0 = DeviceReq(label="to_guest1")

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))
    host2.tap0 = DeviceReq(label="to_guest2")

    guest1 = HostReq()
    guest1.eth0 = DeviceReq(label="to_guest1")

    guest2 = HostReq()
    guest2.eth0 = DeviceReq(label="to_guest2")

    vlan_id = Param(default=10)

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="off", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="on", gso="off", tso="off", tx="on", rx="on"),
        dict(gro="on", gso="on", tso="off", tx="off", rx="on"),
        dict(gro="on", gso="on", tso="on", tx="on", rx="off")))

    def test_wide_configuration(self):
        host1, host2, guest1, guest2 = (self.matched.host1,
            self.matched.host2, self.matched.guest1, self.matched.guest2)

        for host in [host1, host2]:
            host.br0 = BridgeDevice()
            for dev in [host.eth0, host.tap0]:
                dev.down()
                host.br0.slave_add(dev)

        guest1.eth0.down()
        guest2.eth0.down()

        guest1.vlan0 = VlanDevice(realdev=guest1.eth0, vlan_id=self.params.vlan_id)
        guest2.vlan0 = VlanDevice(realdev=guest2.eth0, vlan_id=self.params.vlan_id)

        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = [guest1.vlan0, guest2.vlan0,
            host1.br0, host2.br0]

        net_addr_1 = "192.168.10"
        net_addr6_1 = "fc00:0:0:1"
        host1.br0.ip_add(ipaddress(net_addr_1 + ".1/24"))
        host2.br0.ip_add(ipaddress(net_addr_1 + ".2/24"))

        for i, guest in enumerate([guest1, guest2]):
            guest.vlan0.ip_add(ipaddress(net_addr_1 + "." + str(i+3) +
                "/24"))
            guest.vlan0.ip_add(ipaddress(net_addr6_1 + "::" + str(i+3) +
                "/64"))

        for host in [host1, host2]:
            for dev in [host.eth0, host.tap0, host.br0]:
                dev.up()
        for guest in [guest1, guest2]:
            guest.eth0.up()
            guest.vlan0.up()

        if "perf_tool_cpu" in self.params:
            logging.info("'perf_tool_cpu' param (%d) to be set to None" %
                self.params.perf_tool_cpu)
            self.params.perf_tool_cpu = None

        self.wait_tentative_ips(configuration.test_wide_devices)

        return configuration

    def generate_test_wide_description(self, config):
        host1, host2, guest1, guest2 = (self.matched.host1,
            self.matched.host2, self.matched.guest1, self.matched.guest2)
        desc = super().generate_test_wide_description(config)
        desc += [
            "\n".join([
                "Configured {}.{}.ips = {}".format(
                    dev.host.hostid, dev.name, dev.ips
                )
                for dev in config.test_wide_devices
            ]),
            "\n".join([
                "Configured {}.{}.vlan_id = {}".format(
                    dev.host.hostid, dev.name, dev.vlan_id
                )
                for dev in [guest1.vlan0, guest2.vlan0]
            ]),
            "\n".join([
                "Configured {}.{}.realdev = {}".format(
                    dev.host.hostid, dev.name,
                    '.'.join([dev.host.hostid, dev.realdev.name])
                )
                for dev in [guest1.vlan0, guest2.vlan0]
            ]),
            "\n".join([
                "Configured {}.{}.slaves = {}".format(
                    dev.host.hostid, dev.name,
                    ['.'.join([dev.host.hostid, slave.name])
                    for slave in dev.slaves]
                )
                for dev in [host1.br0, host2.br0]
            ])
        ]
        return desc

    def test_wide_deconfiguration(self, config):
        del config.test_wide_devices

        super().test_wide_deconfiguration(config)

    def generate_ping_endpoints(self, config):
        return [PingEndpoints(self.matched.guest1.vlan0, self.matched.guest2.vlan0)]

    def generate_perf_endpoints(self, config):
        return [(self.matched.guest1.vlan0, self.matched.guest2.vlan0)]

    @property
    def offload_nics(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0,
            self.matched.guest1.eth0, self.matched.guest2.eth0]

    @property
    def mtu_hw_config_dev_list(self):
        host1, host2, guest1, guest2 = (self.matched.host1,
            self.matched.host2, self.matched.guest1, self.matched.guest2)
        result = []
        for host in [host1, host2]:
            for dev in [host.eth0, host.tap0, host.br0]:
                result.append(dev)
        for guest in [guest1, guest2]:
            for dev in [guest.eth0, guest.vlan0]:
                result.append(dev)
        return result

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
