"""
Implements scenario similar to regression_tests/phase1/
({round_robin, active_backup}_double_bond.xml + bonding_test.py).
"""
from lnst.Common.Parameters import Param, StrParam, IntParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Devices import BondDevice

class DoubleBondRecipe(BaseEnrtRecipe):
    m1 = HostReq()
    m1.eth0 = DeviceReq(label="net1")
    m1.eth1 = DeviceReq(label="net1")

    m2 = HostReq()
    m2.eth0 = DeviceReq(label="net1")
    m2.eth1 = DeviceReq(label="net1")

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on"),
        dict(gro="off", gso="on", tso="on", tx="on"),
        dict(gro="on", gso="off", tso="off", tx="on"),
        dict(gro="on", gso="on", tso="off", tx="off")))

    bonding_mode = StrParam(mandatory=True)
    miimon_value = IntParam(mandatory=True)

    def test_wide_configuration(self):
        m1, m2 = self.matched.m1, self.matched.m2

        for m in (m1, m2):
            m.bond = BondDevice(mode=self.params.bonding_mode, miimon=self.params.miimon_value)
            m.eth0.down()
            m.eth1.down()
            m.bond.slave_add(m.eth0)
            m.bond.slave_add(m.eth1)

        configuration = EnrtConfiguration()
        configuration.endpoint1 = m1.bond
        configuration.endpoint2 = m2.bond

        if "mtu" in self.params:
            m1.bond.mtu = self.params.mtu
            m2.bond.mtu = self.params.mtu

        net_addr = "192.168.101"
        net_addr6 = "fc00:0:0:0"
        for i, m in enumerate([m1, m2]):
            m.bond.ip_add(ipaddress(net_addr + "." + str(i+1) + "/24"))
            m.bond.ip_add(ipaddress(net_addr6 + "::" + str(i+1) + "/64"))
            m.eth0.up()
            m.eth1.up()
            m.bond.up()

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for m in [m1, m2]:
                m.run("service irqbalance stop")
                for dev in [m.eth0, m.eth1]:
                    self._pin_dev_interrupts(m.eth0, self.params.dev_intr_cpu)

        return configuration

    def test_wide_deconfiguration(self, config):
        m1, m2 = self.matched.m1, self.matched.m2

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for m in [m1, m2]:
                m.run("service irqbalance start")
