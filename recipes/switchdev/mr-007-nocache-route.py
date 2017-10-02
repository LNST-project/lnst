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
import random
from mr_common import MrouteTest

def mcgrp(num):
    return "239.255.%d.%d" % (num/0x100, num%0x100)

def nocache_route(mt, ivif, group, evifs):
    mach_source_port = mt.sw_mach_conn[mt.vif2port[ivif]][0]

    mt.send_mc_traffic(group, mach_source_port, 1)
    mt.expect_mr_notifs(MROUTE.NOTIF_NOCACHE,
                        source_ip = mach_source_port.get_ip(0),
                        source_vif = ivif, group_ip = group)
    source = str(mach_source_port.get_ip(0))
    return mt.mroute_create(source, group, ivif, evifs)

def random_ivif(vifs):
    return random.choice(vifs)

def random_evifs(vifs, ivif):
    evifs = [evif for evif in vifs
             if random.choice([True, False]) and evif != ivif]
    return evifs

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
    vifs = [0, 1, 2, 3, 4]

    mroutes = []
    for i in range(1, 10):
        ivif = random_ivif(vifs)
        evifs = random_evifs(vifs, ivif)
        mroutes.append(nocache_route(mt, ivif, mcgrp(i), evifs))

    for mroute in mroutes:
        mt.mroute_remove(mroute)

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
