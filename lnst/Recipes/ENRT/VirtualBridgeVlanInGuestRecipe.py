import logging
from lnst.Common.Parameters import Param, IntParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Devices import VlanDevice
from lnst.Devices.VlanDevice import VlanDevice as Vlan
from lnst.Devices import BridgeDevice

class VirtualBridgeVlanInGuestRecipe(CommonHWSubConfigMixin,
    OffloadSubConfigMixin, BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))
    host1.tap0 = DeviceReq(label="to_guest")

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    guest1 = HostReq()
    guest1.eth0 = DeviceReq(label="to_guest")

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="off", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="on", gso="off", tso="off", tx="on", rx="on"),
        dict(gro="on", gso="on", tso="off", tx="off", rx="on"),
        dict(gro="on", gso="on", tso="on", tx="on", rx="off")))

    def test_wide_configuration(self):
        host1, host2, guest1 = (self.matched.host1, self.matched.host2,
            self.matched.guest1)

        host1.br0 = BridgeDevice()
        for dev in [host1.eth0, host1.tap0]:
            dev.down()
            host1.br0.slave_add(dev)

        host2.eth0.down()
        guest1.eth0.down()

        host2.vlan0 = VlanDevice(realdev=host2.eth0, vlan_id=10)
        guest1.vlan0 = VlanDevice(realdev=guest1.eth0, vlan_id=10)

        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = [guest1.vlan0, host1.br0,
            host2.vlan0]

        net_addr_1 = "192.168.10"
        net_addr6_1 = "fc00:0:0:1"

        host1.br0.ip_add(ipaddress(net_addr_1 + ".1/24"))
        for i, machine in enumerate([host2, guest1]):
            machine.vlan0.ip_add(ipaddress(net_addr_1 + "." + str(i+2) +
                "/24"))
            machine.vlan0.ip_add(ipaddress(net_addr6_1 + "::" + str(i+2) +
                "/64"))

        for dev in [host1.eth0, host1.tap0, host1.br0, host2.eth0,
                    host2.vlan0, guest1.eth0, guest1.vlan0]:
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
                "Configured {}.{}.vlan_id = {}".format(
                    dev.host.hostid, dev.name, dev.vlan_id
                )
                for dev in config.test_wide_devices if isinstance(dev,
                    Vlan)
            ]),
            "\n".join([
                "Configured {}.{}.realdev = {}".format(
                    dev.host.hostid, dev.name,
                    '.'.join([dev.host.hostid, dev.realdev.name])
                )
                for dev in config.test_wide_devices if isinstance(dev,
                    Vlan)
            ]),
            "Configured {}.{}.slaves = {}".format(
                host1.hostid, host1.br0.name,
                ['.'.join([host1.hostid, slave.name])
                for slave in host1.br0.slaves]
            )
        ]
        return desc

    def test_wide_deconfiguration(self, config):
        del config.test_wide_devices

        super().test_wide_deconfiguration(config)

    def generate_ping_endpoints(self, config):
        return [PingEndpoints(self.matched.guest1.vlan0, self.matched.host2.vlan0)]

    def generate_perf_endpoints(self, config):
        return [(self.matched.guest1.vlan0, self.matched.host2.vlan0)]

    @property
    def offload_nics(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0,
            self.matched.guest1.eth0]

    @property
    def mtu_hw_config_dev_list(self):
        host1, host2, guest1 = (self.matched.host1, self.matched.host2,
            self.matched.guest1)
        return [host1.eth0, host1.tap0, host1.br0, guest1.eth0,
            host2.eth0, host2.vlan0, guest1.vlan0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
