"""
Implements scenario similar to regression_tests/phase1/
(virtual_bridge_2_vlans_over_active_backup_bond.xml + virtual_bridge_2_vlans_over_bond.py)
"""
from lnst.Common.Parameters import Param, IntParam, StrParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Devices import VlanDevice
from lnst.Devices import BondDevice
from lnst.Devices import BridgeDevice

class VirtualBridgeVlansOverBondRecipe(BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch")
    host1.eth1 = DeviceReq(label="to_switch")
    host1.tap0 = DeviceReq(label="to_guest1")
    host1.tap1 = DeviceReq(label="to_guest2")

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch")
    host2.eth1 = DeviceReq(label="to_switch")
    host2.tap0 = DeviceReq(label="to_guest3")
    host2.tap1 = DeviceReq(label="to_guest4")

    guest1 = HostReq()
    guest1.eth0 = DeviceReq(label="to_guest1")

    guest2 = HostReq()
    guest2.eth0 = DeviceReq(label="to_guest2")

    guest3 = HostReq()
    guest3.eth0 = DeviceReq(label="to_guest3")

    guest4 = HostReq()
    guest4.eth0 = DeviceReq(label="to_guest4")

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on"),
        dict(gro="off", gso="on", tso="on", tx="on"),
        dict(gro="on", gso="off", tso="off", tx="on"),
        dict(gro="on", gso="on", tso="off", tx="on")))

    bonding_mode = StrParam(mandatory=True)
    miimon_value = IntParam(mandatory=True)

    def test_wide_configuration(self):
        host1, host2, guest1, guest2, guest3, guest4 = self.matched.host1, self.matched.host2, self.matched.guest1, self.matched.guest2, self.matched.guest3, self.matched.guest4

        for m, n in [(host1, 10),(host2, 10)]:
            m.eth0.down()
            m.eth1.down()
            m.tap0.down()
            m.tap1.down()
            m.bond = BondDevice(mode=self.params.bonding_mode, miimon=self.params.miimon_value)
            m.bond.slave_add(m.eth0)
            m.bond.slave_add(m.eth1)
            m.vlan1 = VlanDevice(realdev=m.bond, vlan_id=n)
            m.vlan2 = VlanDevice(realdev=m.bond, vlan_id=2*n)
            m.br0 = BridgeDevice()
            m.br0.slave_add(m.vlan1)
            m.br0.slave_add(m.tap0)
            m.br1 = BridgeDevice()
            m.br1.slave_add(m.vlan2)
            m.br1.slave_add(m.tap1)

        for m in (guest1, guest2, guest3, guest4):
            m.eth0.down()

        #Due to limitations in the current EnrtConfiguration
        #class, a single vlan test pair is chosen
        configuration = EnrtConfiguration()
        configuration.endpoint1 = guest1.eth0
        configuration.endpoint2 = guest3.eth0

        if "mtu" in self.params:
            host1.bond.mtu = self.params.mtu
            host1.tap0.mtu = self.params.mtu
            host1.tap1.mtu = self.params.mtu
            host1.vlan1.mtu = self.params.mtu
            host1.vlan2.mtu = self.params.mtu
            host1.br0.mtu = self.params.mtu
            host1.br1.mtu = self.params.mtu
            host2.bond.mtu = self.params.mtu
            host2.tap0.mtu = self.params.mtu
            host2.tap1.mtu = self.params.mtu
            host2.vlan1.mtu = self.params.mtu
            host2.vlan2.mtu = self.params.mtu
            host2.br0.mtu = self.params.mtu
            host2.br1.mtu = self.params.mtu
            guest1.eth0.mtu = self.params.mtu
            guest2.eth0.mtu = self.params.mtu
            guest3.eth0.mtu = self.params.mtu
            guest4.eth0.mtu = self.params.mtu

        net_addr_1 = "192.168.10"
        net_addr_2 = "192.168.20"
        net_addr6_1 = "fc00:0:0:1"
        net_addr6_2 = "fc00:0:0:2"

        for m, (g1, g2), n in [(host1, (guest1, guest2), 1), (host2, (guest3, guest4), 3)]:
            m.bond.ip_add(ipaddress("1.2.3.4"))
            m.br0.ip_add(ipaddress(net_addr_1 + "." + str(n) + "/24"))
            m.br1.ip_add(ipaddress(net_addr_2 + "." + str(n) + "/24"))
            g1.eth0.ip_add(ipaddress(net_addr_1 + "." + str(n+1) + "/24"))
            g1.eth0.ip_add(ipaddress(net_addr6_1 + "::" + str(n+1) + "/64"))
            g2.eth0.ip_add(ipaddress(net_addr_2 + "." + str(n+1) + "/24"))
            g2.eth0.ip_add(ipaddress(net_addr6_2 + "::" + str(n+1) + "/64"))

        for m, g1, g2 in [(host1, guest1, guest2), (host2, guest3, guest4)]:
            m.eth0.up()
            m.eth1.up()
            m.tap0.up()
            m.tap1.up()
            m.bond.up()
            m.vlan1.up()
            m.vlan2.up()
            m.br0.up()
            m.br1.up()
            g1.eth0.up()
            g2.eth0.up()

        #TODO better service handling through HostAPI
        for m in (host1, host2, guest1, guest2, guest3, guest4):
            host1.run("service irqbalance stop")

        for m in self.matched:
            for dev in m.devices:
                self._pin_dev_interrupts(dev, self.params.dev_intr_cpu)

        return configuration

    def test_wide_deconfiguration(self, config):
        host1, host2, guest1, guest2, guest3, guest4 = self.matched.host1, self.matched.host2, self.matched.guest1, self.matched.guest2, self.matched.guest3, self.matched.guest4

        #TODO better service handling through HostAPI
        for m in (host1, host2, guest1, guest2, guest3, guest4):
            host1.run("service irqbalance start")
