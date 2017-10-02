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
import random

MANY_ROUTES = 100
SOME_ROUTES = 20

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
    mt.pimreg_add(5)

    # add many (S,G) routes
    sg_mroutes = []
    for i in range(MANY_ROUTES):
        sg = mt.random_mroute_add(mcgrp(i + 1), False, test = False)
        sg_mroutes.append(sg)

    # add many (*,G) routes
    starg_mroutes = []
    for i in range(MANY_ROUTES):
        starg = mt.random_mroute_add(mcgrp(MANY_ROUTES + i + 1), True,
                                     test = False)
        starg_mroutes.append(starg)

    # create a shuffled route list
    mroutes = sg_mroutes + starg_mroutes
    random.shuffle(mroutes)

    # test some routes
    some_mroutes = mroutes[:SOME_ROUTES]
    for mroute in some_mroutes:
        mt.mroute_test(mroute)

    # unresolve a VIFs
    mt.del_vif(2)

    # test some routes
    some_mroutes = mroutes[:SOME_ROUTES]
    for mroute in some_mroutes:
        mt.mroute_test(mroute)

    # Remove all VIFs
    mt.del_vif(0)
    mt.del_vif(1)
    mt.del_vif(3)
    mt.del_vif(4)

    # delete all in random order, as mroutes is shuffled
    for mroute in mroutes:
        mt.mroute_remove(mroute, test = False)

    mt.fini()

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
