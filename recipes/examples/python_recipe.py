#!/bin/python2
"""
This is an example python recipe that can be run as an executable script.
Performs a simple ping between two hosts.
"""

from lnst.Common.Parameters import IpParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import Controller
from lnst.Controller import BaseRecipe
from lnst.Controller import HostReq, DeviceReq

from lnst.Tests import IcmpPing

class MyRecipe(BaseRecipe):
    m1 = HostReq()
    m1.eth0 = DeviceReq(label="net1")

    m2 = HostReq()
    m2.eth0 = DeviceReq(label="net1")

    def test(self):
        self.matched.m1.eth0.ip_add(ipaddress("192.168.1.1/24"))
        self.matched.m1.eth0.up()
        self.matched.m2.eth0.ip_add(ipaddress("192.168.1.2/24"))
        self.matched.m2.eth0.up()
        ping_job = self.matched.m1.run(IcmpPing(dst=self.matched.m2.eth0,
                                                interval=0,
                                                iface=self.matched.m1.eth0))

ctl = Controller(debug=1)

r = MyRecipe()
ctl.run(r, allow_virt=True)
