"""
Implements scenario similar to regression_tests/phase1/
(virtual_bridge_vlan_in_host.xml + virtual_bridge_vlan_in_host.py)
"""
from lnst.Common.Parameters import Param
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Devices import VlanDevice
from lnst.Devices import BridgeDevice

class VirtualBridgeVlanInHostRecipe(BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch")
    host1.tap0 = DeviceReq(label="to_guest")

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch")

    guest1 = HostReq()
    guest1.eth0 = DeviceReq(label="to_guest")

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="off", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="on", gso="off", tso="off", tx="on", rx="on"),
        dict(gro="on", gso="on", tso="off", tx="off", rx="on"),
        dict(gro="on", gso="on", tso="on", tx="on", rx="off")))

    def test_wide_configuration(self):
        host1, host2, guest1 = self.matched.host1, self.matched.host2, self.matched.guest1

        host1.eth0.down()
        host1.tap0.down()
        host1.vlan1 = VlanDevice(realdev=host1.eth0, vlan_id=10)
        host1.br0 = BridgeDevice()
        host1.br0.slave_add(host1.vlan1)
        host1.br0.slave_add(host1.tap0)

        host2.eth0.down()
        host2.vlan1 = VlanDevice(realdev=host2.eth0, vlan_id=10)

        guest1.eth0.down()

        configuration = EnrtConfiguration()
        configuration.endpoint1 = guest1.eth0
        configuration.endpoint2 = host2.vlan1

        if "mtu" in self.params:
            host1.eth0.mtu = self.params.mtu
            host1.tap0.mtu = self.params.mtu
            host1.vlan1.mtu = self.params.mtu
            host1.br0.mtu = self.params.mtu
            host2.eth0.mtu = self.params.mtu
            host2.vlan1.mtu = self.params.mtu
            guest1.eth0.mtu = self.params.mtu

        net_addr_1 = "192.168.10"
        net_addr6_1 = "fc00:0:0:1"

        host1.br0.ip_add(ipaddress(net_addr_1 + ".1/24"))
        host2.vlan1.ip_add(ipaddress(net_addr_1 + ".2/24"))
        host2.vlan1.ip_add(ipaddress(net_addr6_1 + "::2/64"))
        guest1.eth0.ip_add(ipaddress(net_addr_1 + ".3/24"))
        guest1.eth0.ip_add(ipaddress(net_addr6_1 + "::3/64"))

        host1.eth0.up()
        host1.tap0.up()
        host1.vlan1.up()
        host1.br0.up()
        host2.eth0.up()
        host2.vlan1.up()
        guest1.eth0.up()

        #TODO better service handling through HostAPI
        host1.run("service irqbalance stop")
        host2.run("service irqbalance stop")
        guest1.run("service irqbalance stop")

        for m in self.matched:
            for dev in m.devices:
                self._pin_dev_interrupts(dev, self.params.dev_intr_cpu)

        return configuration

    def test_wide_deconfiguration(self, config):
        host1, host2, guest1 = self.matched.host1, self.matched.host2, self.matched.guest1

        #TODO better service handling through HostAPI
        host1.run("service irqbalance start")
        host2.run("service irqbalance start")
        guest1.run("service irqbalance start")
