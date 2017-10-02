"""
Copyright 2017 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
yotamg@mellanox.com (Yotam Gigi)
"""

from lnst.Controller.Task import ctl
from lnst.Common.Consts import MROUTE
from TestLib import TestLib
from time import sleep
from mr_common import MrouteTest

def test_ip(major, minor):
    return ["192.168.%d.%d" % (major, minor),
            "2002:%d::%d" % (major, minor)]
def ipv4(ip):
    return ip[0]

def mcgrp(num):
    return "239.255.%d.%d" % (num/0x100, num%0x100)

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m1_if2, m2_if1, m2_if2, m2_if3, m2_if4, sw_if1, \
    sw_br_m1, sw_br_m2, sw_if3, sw_if4, sw_if5, sw_if2 = ifaces

    sw_ports = [sw_if1, sw_if2, sw_if3, sw_if4, sw_if5]

    tl = TestLib(ctl, aliases)
    mt = MrouteTest(tl, hosts, ifaces)

    sleep(30)
    mt.init()

    # add vifs
    mt.add_vif(sw_if1, 0)
    mt.add_vif(sw_if2, 1)
    mt.add_vif(sw_if3, 2)
    mt.add_vif(sw_if4, 3)
    mt.add_vif(sw_if5, 4)

    # add an (S,G) route
    evifs = [0, 1, 2]
    sg = mt.mroute_create(ipv4(test_ip(5,2)), mcgrp(1), 4, evifs)

    # remove RIF
    mt.del_rif(sw_if3)

    # add it back
    mt.add_rif(sw_if3)
    sleep(30)
    mt.mroute_test(sg)

    # remove another RIF
    mt.del_rif(sw_if1)

    mt.mroute_remove(sg)
    mt.fini()
    return

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine1").get_interface("if2"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if2"),
         ctl.get_host("machine2").get_interface("if3"),
         ctl.get_host("machine2").get_interface("if4"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2"),
         ctl.get_host("switch").get_interface("if3"),
         ctl.get_host("switch").get_interface("if4"),
         ctl.get_host("switch").get_interface("if5"),
         ctl.get_host("switch").get_interface("if6"),
         ctl.get_host("switch").get_interface("br0")],
        ctl.get_aliases())
