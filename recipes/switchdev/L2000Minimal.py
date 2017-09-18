#!/bin/python

"""
Copyright 2016-2017 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jiri@mellanox.com (Jiri Pirko)
"""

from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq
from lnst.Devices import BridgeDevice
from SwitchdevRecipe import SwitchdevRecipe
from SwitchdevRecipe import run_switchdev_recipe
from time import sleep

class L2000Minimal(SwitchdevRecipe):
    m1 = HostReq()
    m1.if1 = DeviceReq(label="net1")
    m2 = HostReq()
    m2.if1 = DeviceReq(label="net2")
    sw = HostReq()
    sw.if1 = DeviceReq(label="net1")
    sw.if2 = DeviceReq(label="net2")

    def test(self):
        m1 = self.matched.m1
        m2 = self.matched.m2
        sw = self.matched.sw

        m1.if1.ip_add([ipaddress("192.168.101.10/24"), ipaddress("2002::1/64")])
        m2.if1.ip_add([ipaddress("192.168.101.11/24"), ipaddress("2002::2/64")])
        m1.if1.up()
        m2.if1.up()

        sw.br1 = BridgeDevice(vlan_filtering=1)
        sw.br1.slave_add(sw.if1)
        sw.br1.slave_add(sw.if2)
        sw.if1.up()
        sw.if2.up()
        sw.br1.up()

        sleep(15)

        self.tl.ping_simple(m1.if1, m2.if1)

if __name__ == "__main__":
    run_switchdev_recipe(L2000Minimal)
