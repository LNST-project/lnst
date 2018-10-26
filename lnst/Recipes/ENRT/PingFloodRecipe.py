#!/bin/python2
"""
Implements scenario similar to regression_tests/phase1/
(ping_flood.xml + simple_ping.py).
"""

from lnst.Common.Parameters import Param, IntParam, StrParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq
from lnst.RecipeCommon.Ping import PingConf, PingTestAndEvaluate

class PingFloodRecipe(PingTestAndEvaluate):
    m1 = HostReq()
    m1.eth0 = DeviceReq(label="net1")

    m2 = HostReq()
    m2.eth0 = DeviceReq(label="net1")

    #TODO: use a parameter for the network
    src_addr = StrParam(default = "192.168.1.1/24")
    dst_addr = StrParam(default = "192.168.1.2/24")
    count = IntParam(default = 100)
    interval = StrParam(default = 0.2)
    size = IntParam(default = None)

    def test(self):
        m1, m2 = self.matched.m1, self.matched.m2

        m1.eth0.ip_add(ipaddress(self.params.src_addr))
        m2.eth0.ip_add(ipaddress(self.params.dst_addr))

        if "mtu" in self.params:
            m1.eth0.mtu = self.params.mtu
            m2.eth0.mtu = self.params.mtu

        m1.eth0.up()
        m2.eth0.up()

        if1 = m1.eth0
        ip2 = m2.eth0.ips[0]
        cn = self.params.count
        iv = self.params.interval
        sz = self.params.size

        pcfg=PingConf(m1, if1, m2, ip2, count = cn, interval = iv, size = sz or None)

        result = self.ping_test(pcfg)
        self.ping_evaluate_and_report(pcfg, result)
