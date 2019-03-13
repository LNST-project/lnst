"""
Implements scenario similar to regression_tests/phase2/
(3_vlans_over_{active_backup,round_robin}_team.xml + 3_vlans_over_team.py)
"""
from lnst.Common.Parameters import Param, IntParam, StrParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Devices import VlanDevice
from lnst.Devices import TeamDevice

class VlansOverTeamRecipe(BaseEnrtRecipe):
    m1 = HostReq()
    m1.eth1 = DeviceReq(label="tnet")
    m1.eth2 = DeviceReq(label="tnet")

    m2 = HostReq()
    m2.eth1 = DeviceReq(label="tnet")

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on"),
        dict(gro="off", gso="on", tso="on", tx="on"),
        dict(gro="on", gso="off", tso="off", tx="on"),
        dict(gro="on", gso="on", tso="off", tx="off")))

    runner_name = StrParam(mandatory = True)

    def test_wide_configuration(self):
        m1, m2 = self.matched.m1, self.matched.m2

        m1.eth1.down()
        m1.eth2.down()
        #The config argument needs to be used with a team device normally (e.g  to specify
        #the runner mode), but it is not used here due to a bug in the TeamDevice module
        m1.team = TeamDevice()
        m1.team.slave_add(m1.eth1)
        m1.team.slave_add(m1.eth2)
        m1.vlan1 = VlanDevice(realdev=m1.team, vlan_id=10)
        m1.vlan2 = VlanDevice(realdev=m1.team, vlan_id=20)

        m2.vlan1 = VlanDevice(realdev=m2.eth1, vlan_id=10)
        m2.vlan2 = VlanDevice(realdev=m2.eth1, vlan_id=20)

        #Due to limitations in the current EnrtConfiguration
        #class, a single vlan test pair is chosen
        configuration = EnrtConfiguration()
        configuration.endpoint1 = m1.vlan1
        configuration.endpoint2 = m2.vlan1

        if "mtu" in self.params:
            for m in (m1, m2):
                m.vlan1.mtu = self.params.mtu
                m.vlan2.mtu = self.params.mtu
            m1.team.mtu = self.params.mtu
            m2.eth1.mtu = self.params.mtu

        net_addr_1 = "192.168.10"
        net_addr_2 = "192.168.20"
        net_addr6_1 = "fc00:0:0:1"
        net_addr6_2 = "fc00:0:0:2"

        m1.team.ip_add(ipaddress("1.2.3.4/24"))
        for i, m in enumerate([m1, m2]):
            m.vlan1.ip_add(ipaddress(net_addr_1 + "." + str(i+1) + "/24"))
            m.vlan1.ip_add(ipaddress(net_addr6_1 + "::" + str(i+1) + "/64"))
            m.vlan2.ip_add(ipaddress(net_addr_2 + "." + str(i+1) + "/24"))
            m.vlan2.ip_add(ipaddress(net_addr6_2 + "::" + str(i+1) + "/64"))

        m1.eth1.up()
        m1.eth2.up()
        m1.team.up()
        m1.vlan1.up()
        m1.vlan2.up()
        m2.eth1.up()
        m2.vlan1.up()
        m2.vlan2.up()

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for m in [m1, m2]:
                m.run("service irqbalance stop")
            for dev in [m1.eth1, m1.eth2, m2.eth1]:
                self._pin_dev_interrupts(dev, self.params.dev_intr_cpu)

        return configuration

    def test_wide_deconfiguration(self, config):
        m1, m2 = self.matched.m1, self.matched.m2

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for m in [m1, m2]:
                m.run("service irqbalance start")
