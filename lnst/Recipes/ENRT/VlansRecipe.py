"""
Implements scenario similar to regression_tests/phase1/
(3_vlans.xml + 3_vlans.py), but 2 Vlans are used
"""
from lnst.Common.Parameters import Param
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Devices import VlanDevice

class VlansRecipe(BaseEnrtRecipe):
    m1 = HostReq()
    m1.eth0 = DeviceReq(label="net1")

    m2 = HostReq()
    m2.eth0 = DeviceReq(label="net1")

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="off", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="on", gso="off", tso="off", tx="on", rx="on"),
        dict(gro="on", gso="on", tso="off", tx="off", rx="on"),
        dict(gro="on", gso="on", tso="on", tx="on", rx="off")))

    def test_wide_configuration(self):
        m1, m2 = self.matched.m1, self.matched.m2

        m1.eth0.down()
        m1.vlan1 = VlanDevice(realdev=m1.eth0, vlan_id=10)
        m1.vlan2 = VlanDevice(realdev=m1.eth0, vlan_id=20)

        m2.eth0.down()
        m2.vlan1 = VlanDevice(realdev=m2.eth0, vlan_id=10)
        m2.vlan2 = VlanDevice(realdev=m2.eth0, vlan_id=20)

        #Due to limitations in the current EnrtConfiguration
        #class, a single vlan test pair is chosen
        configuration = EnrtConfiguration()
        configuration.endpoint1 = m1.vlan1
        configuration.endpoint2 = m2.vlan1

        if "mtu" in self.params:
            m1.eth0.mtu = self.params.mtu
            m2.eth0.mtu = self.params.mtu
            m1.vlan1.mtu = self.params.mtu
            m1.vlan2.mtu = self.params.mtu
            m2.vlan1.mtu = self.params.mtu
            m2.vlan2.mtu = self.params.mtu

        net_addr_1 = "192.168.10"
        net_addr_2 = "192.168.20"
        net_addr6_1 = "fc00:0:0:1"
        net_addr6_2 = "fc00:0:0:2"

        for i, m in enumerate([m1, m2]):
            m.vlan1.ip_add(ipaddress(net_addr_1 + "." + str(i+1) + "/24"))
            m.vlan1.ip_add(ipaddress(net_addr6_1 + "::" + str(i+1) + "/64"))
            m.vlan2.ip_add(ipaddress(net_addr_2 + "." + str(i+1) + "/24"))
            m.vlan2.ip_add(ipaddress(net_addr6_2 + "::" + str(i+1) + "/64"))

        m1.eth0.up()
        m1.vlan1.up()
        m1.vlan2.up()
        m2.eth0.up()
        m2.vlan1.up()
        m2.vlan2.up()

        if "adaptive_rx_coalescing" in self.params:
            for m in [m1, m2]:
                m.eth0.adaptive_rx_coalescing = self.params.adaptive_rx_coalescing
        if "adaptive_tx_coalescing" in self.params:
            for m in [m1, m2]:
                m.eth0.adaptive_tx_coalescing = self.params.adaptive_tx_coalescing

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for m in [m1, m2]:
                m.run("service irqbalance stop")
                self._pin_dev_interrupts(m.eth0, self.params.dev_intr_cpu)

        return configuration

    def test_wide_deconfiguration(self, config):
        m1, m2 = self.matched.m1, self.matched.m2

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for m in [m1, m2]:
                m.run("service irqbalance start")
