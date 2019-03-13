"""
Implements scenario similar to regression_tests/phase2/
({active_backup,round_robin}_double_team.xml + team_test.py)
"""
from lnst.Common.Parameters import Param, IntParam, StrParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Devices import TeamDevice

class DoubleTeamRecipe(BaseEnrtRecipe):
    m1 = HostReq()
    m1.eth1 = DeviceReq(label="tnet")
    m1.eth2 = DeviceReq(label="tnet")

    m2 = HostReq()
    m2.eth1 = DeviceReq(label="tnet")
    m2.eth2 = DeviceReq(label="tnet")

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on"),
        dict(gro="off", gso="on", tso="on", tx="on"),
        dict(gro="on", gso="off", tso="off", tx="on"),
        dict(gro="on", gso="on", tso="off", tx="off")))

    runner_name = StrParam(mandatory=True)

    def test_wide_configuration(self):
        m1, m2 = self.matched.m1, self.matched.m2

        m1.eth1.down()
        m1.eth2.down()
        #The config argument needs to be used with a team device normally (e.g  to specify
        #the runner mode), but it is not used here due to a bug in the TeamDevice module
        m1.team = TeamDevice()
        m1.team.slave_add(m1.eth1)
        m1.team.slave_add(m1.eth2)

        m2.eth1.down()
        m2.eth2.down()
        m2.team = TeamDevice()
        m2.team.slave_add(m2.eth1)
        m2.team.slave_add(m2.eth2)

        #EnrtConfiguration and both-side Netperf config need to be checked
        configuration = EnrtConfiguration()
        configuration.endpoint1 = m1.team
        configuration.endpoint2 = m2.team

        if "mtu" in self.params:
            m1.team.mtu = self.params.mtu
            m2.team.mtu = self.params.mtu

        net_addr_1 = "192.168.10"
        net_addr6_1 = "fc00:0:0:1"

        m1.team.ip_add(ipaddress(net_addr_1 + ".1/24"))
        m1.team.ip_add(ipaddress(net_addr6_1 + "::1/64"))
        m2.team.ip_add(ipaddress(net_addr_1 + ".2/24"))
        m2.team.ip_add(ipaddress(net_addr6_1 + "::2/64"))

        m1.eth1.up()
        m1.eth2.up()
        m1.team.up()
        m2.eth1.up()
        m2.eth2.up()
        m2.team.up()

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for m in [m1, m2]:
                m.run("service irqbalance stop")
                for dev in [m.eth1, m.eth2]:
                    self._pin_dev_interrupts(dev, self.params.dev_intr_cpu)

        return configuration

    def test_wide_deconfiguration(self, config):
        m1, m2 = self.matched.m1, self.matched.m2

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for m in [m1, m2]:
                m.run("service irqbalance start")
