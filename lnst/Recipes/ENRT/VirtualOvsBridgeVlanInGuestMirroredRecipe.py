"""
Implements scenario similar to regression_tests/phase2/
(virtual_ovs_bridge_vlan_in_guest_mirrored.xml + virtual_ovs_bridge_vlan_in_guest_mirrored.py
)
"""
from lnst.Common.Parameters import Param
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Devices import VlanDevice
from lnst.Devices import OvsBridgeDevice

class VirtualOvsBridgeVlanInGuestMirroredRecipe(BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth1 = DeviceReq(label="to_switch")
    host1.tap0 = DeviceReq(label="to_guest1")

    host2 = HostReq()
    host2.eth1 = DeviceReq(label="to_switch")
    host2.tap0 = DeviceReq(label="to_guest2")

    guest1 = HostReq()
    guest1.tap0 = DeviceReq(label="to_guest1")

    guest2 = HostReq()
    guest2.tap0 = DeviceReq(label="to_guest2")

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="off", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="on", gso="off", tso="off", tx="on", rx="on"),
        dict(gro="on", gso="on", tso="off", tx="off", rx="on"),
        dict(gro="on", gso="on", tso="on", tx="on", rx="off")))

    def test_wide_configuration(self):
        host1, host2, guest1, guest2 = self.matched.host1, self.matched.host2, self.matched.guest1, self.matched.guest2

        host1.eth1.down()
        host1.tap0.down()
        host1.br0 = OvsBridgeDevice()
        for m, d in [(host1, host1.eth1), (host1, host1.tap0)]:
            m.br0.port_add(d)

        host2.eth1.down()
        host2.tap0.down()
        host2.br0 = OvsBridgeDevice()
        for m, d in [(host2, host2.eth1), (host2, host2.tap0)]:
            if d.master != None:
                if "ovs" not in d.master.name:
                    m.br0.port_add(d)
            else:
                m.br0.port_add(d)

        guest1.tap0.down()
        guest1.vlan1 = VlanDevice(realdev=guest1.tap0, vlan_id=10)

        guest2.tap0.down()
        guest2.vlan1 = VlanDevice(realdev=guest2.tap0, vlan_id=10)

        #Due to limitations in the current EnrtConfiguration
        #class, a single vlan test pair is chosen
        configuration = EnrtConfiguration()
        configuration.endpoint1 = guest1.vlan1
        configuration.endpoint2 = guest2.vlan1

        if "mtu" in self.params:
            host1.br0.mtu = self.params.mtu
            host2.br0.mtu = self.params.mtu
            guest1.vlan1.mtu = self.params.mtu
            guest2.vlan1.mtu = self.params.mtu

        net_addr_1 = "192.168.10"
        net_addr6_1 = "fc00:0:0:1"

        guest1.vlan1.ip_add(ipaddress(net_addr_1 + ".3/24"))
        guest1.vlan1.ip_add(ipaddress(net_addr6_1 + "::3/64"))
        guest2.vlan1.ip_add(ipaddress(net_addr_1 + ".4/24"))
        guest2.vlan1.ip_add(ipaddress(net_addr6_1 + "::4/64"))

        host1.eth1.up()
        host1.tap0.up()
        host1.br0.up()
        host2.eth1.up()
        host2.tap0.up()
        host2.br0.up()
        guest1.tap0.up()
        guest1.vlan1.up()
        guest2.tap0.up()
        guest2.vlan1.up()

        #TODO better service handling through HostAPI
        host1.run("service irqbalance stop")
        host2.run("service irqbalance stop")
        guest1.run("service irqbalance stop")
        guest2.run("service irqbalance stop")

        for m in self.matched:
            for dev in m.devices:
                self._pin_dev_interrupts(dev, self.params.dev_intr_cpu)

        return configuration

    def test_wide_deconfiguration(self, config):
        host1, host2, guest1, guest2 = self.matched.host1, self.matched.host2, self.matched.guest1, self.matched.guest2

        #TODO better service handling through HostAPI
        host1.run("service irqbalance start")
        host2.run("service irqbalance start")
        guest1.run("service irqbalance start")
        guest2.run("service irqbalance start")
