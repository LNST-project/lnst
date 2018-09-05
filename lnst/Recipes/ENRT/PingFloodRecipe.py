#!/bin/python2
"""
Implements scenario similar to regression_tests/phase1/
(ping_flood.xml + simple_ping.py)
"""

from lnst.Common.Parameters import Param
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, BaseRecipe
from lnst.Tests import Ping

#TODO: Inherit just from PingTestAndEvaluate after enabling patch is available
class PingFloodRecipe(BaseRecipe):
    m1 = HostReq()
    m1.eth0 = DeviceReq(label="net1")

    m2 = HostReq()
    m2.eth0 = DeviceReq(label="net1")

    def test(self):
        m1, m2 = self.matched.m1, self.matched.m2

        self.matched.m1.eth0.ip_add(ipaddress("192.168.1.1/24"))
        self.matched.m2.eth0.ip_add(ipaddress("192.168.1.2/24"))

        if "mtu" in self.params:
            self.matched.m1.eth0.mtu = self.params.mtu
            self.matched.m2.eth0.mtu = self.params.mtu

        self.matched.m1.eth0.up()
        self.matched.m2.eth0.up()

        ping_job = self.matched.m1.run(Ping(dst=self.matched.m2.eth0.ips[0], count=100, interval=0.2,
                              interface=self.matched.m1.eth0))
