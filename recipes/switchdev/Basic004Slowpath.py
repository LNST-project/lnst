#!/bin/python

"""
Copyright 2016-2017 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
idosch@mellanox.com (Ido Schimmel)
jiri@mellanox.com (Jiri Pirko)
"""

from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq
from SwitchdevRecipe import SwitchdevRecipe
from SwitchdevRecipe import run_switchdev_recipe
from time import sleep

class Basic004Slowpath(SwitchdevRecipe):
    m1 = HostReq()
    m1.if1 = DeviceReq(label="net1")
    sw = HostReq()
    sw.if1 = DeviceReq(label="net1")

    def test(self):
        m1 = self.matched.m1
        sw = self.matched.sw

        m1.if1.ip_add([ipaddress("192.168.101.10/24"), ipaddress("2002::1/64")])
        sw.if1.ip_add([ipaddress("192.168.101.11/24"), ipaddress("2002::2/64")])
        m1.if1.up()
        sw.if1.up()

        sleep(15)

        self.tl.ping_simple(m1.if1, sw.if1)
        self.tl.netperf_tcp(m1.if1, sw.if1)
        self.tl.netperf_udp(m1.if1, sw.if1)

if __name__ == "__main__":
    run_switchdev_recipe(Basic004Slowpath)
