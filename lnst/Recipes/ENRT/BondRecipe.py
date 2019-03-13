"""
Implements scenario similar to regression_tests/phase1/
({active_backup, round_robin}_bond.xml + bonding_test.py)
"""
from lnst.Common.Parameters import Param, IntParam, StrParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Devices import BondDevice

class BondRecipe(BaseEnrtRecipe):
    m1 = HostReq()
    m1.eth0 = DeviceReq(label="net1")
    m1.eth1 = DeviceReq(label="net1")

    m2 = HostReq()
    m2.eth0 = DeviceReq(label="net1")

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on"),
        dict(gro="off", gso="on", tso="on", tx="on"),
        dict(gro="on", gso="off", tso="off", tx="on"),
        dict(gro="on", gso="on", tso="off", tx="off")))

    bonding_mode = StrParam(mandatory=True)
    miimon_value = IntParam(mandatory=True)

    def test_wide_configuration(self):
        m1, m2 = self.matched.m1, self.matched.m2

        m1.bond0 = BondDevice(mode=self.params.bonding_mode, miimon=self.params.miimon_value)
        m1.eth0.down()
        m1.eth1.down()
        m1.bond0.slave_add(m1.eth0)
        m1.bond0.slave_add(m1.eth1)

        configuration = EnrtConfiguration()
        configuration.endpoint1 = m1.bond0
        configuration.endpoint2 = m2.eth0

        if "mtu" in self.params:
            m1.bond0.mtu = self.params.mtu
            m2.eth0.mtu = self.params.mtu

        net_addr = "192.168.101"
        net_addr6 = "fc00:0:0:0"
        m1.bond0.ip_add(ipaddress(net_addr + ".1/24"))
        m1.bond0.ip_add(ipaddress(net_addr6 + "::1/64"))
        m1.eth0.up()
        m1.eth1.up()
        m1.bond0.up()

        m2.eth0.ip_add(ipaddress(net_addr + ".2/24"))
        m2.eth0.ip_add(ipaddress(net_addr6 + "::2/64"))
        m2.eth0.up()

        if "adaptive_rx_coalescing" in self.params:
            for dev in [m1.eth0, m1.eth1, m2.eth0]:
                dev.adaptive_rx_coalescing = self.params.adaptive_rx_coalescing
        if "adaptive_tx_coalescing" in self.params:
            for dev in [m1.eth0, m1.eth1, m2.eth0]:
                dev.adaptive_tx_coalescing = self.params.adaptive_tx_coalescing

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for m in [m1, m2]:
                m.run("service irqbalance stop")
            for dev in [m1.eth0, m1.eth1, m2.eth0]:
                self._pin_dev_interrupts(dev, self.params.dev_intr_cpu)

        return configuration

    def test_wide_deconfiguration(self, config):
        m1, m2 = self.matched.m1, self.matched.m2

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for m in [m1, m2]:
                m.run("service irqbalance start")
