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
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1")

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="net1")

    #TODO: use a parameter for the network
    src_addr = StrParam(default = "192.168.1.1/24")
    dst_addr = StrParam(default = "192.168.1.2/24")
    count = IntParam(default = 100)
    interval = StrParam(default = 0.2)
    size = IntParam(default = None)

    def test(self):
        host1, host2 = self.matched.host1, self.matched.host2

        host1.eth0.ip_add(ipaddress(self.params.src_addr))
        host2.eth0.ip_add(ipaddress(self.params.dst_addr))

        if "mtu" in self.params:
            host1.eth0.mtu = self.params.mtu
            host2.eth0.mtu = self.params.mtu

        host1.eth0.up()
        host2.eth0.up()

        if1 = host1.eth0
        ip2 = host2.eth0.ips[0]
        cn = self.params.count
        iv = self.params.interval
        sz = self.params.size

        pcfg=PingConf(host1, if1, host2, ip2, count = cn, interval = iv, size = sz or None)

        result = self.ping_test([pcfg])
        self.ping_evaluate_and_report(pcfg, result)
