"""
Copyright 2016 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
nogahf@mellanox.com (Nogah Frankel)
"""

from lnst.Controller.Task import ctl
from TestLib import TestLib
from time import sleep
import logging
from lnst.Common.Consts import MCAST_ROUTER_PORT

def test_ip(major, minor):
    return ["192.168.10%d.%d/24" % (major, minor),
            "2002:%d::%d/64" % (major, minor)]

def mcgrp(i):
    return "239.255.1.%d" % i

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if, m2_if, m3_if, m4_if, sw_if1, sw_if2, sw_if3, sw_if4 = ifaces

    # Create a bridge
    sw_ports = [sw_if1, sw_if2, sw_if3, sw_if4]
    sw_br = sw.create_bridge(slaves = sw_ports, options={"vlan_filtering": 1})

    m1_if.set_addresses(test_ip(1, 1))
    m2_if.set_addresses(test_ip(1, 2))
    m3_if.set_addresses(test_ip(1, 3))
    m4_if.set_addresses(test_ip(1, 4))
    sleep(15)

    tl = TestLib(ctl, aliases)
    for iface in [m1_if, m2_if, m3_if, m4_if]:
        iface.enable_multicast()

    tl._ctl.wait(2)
    tl.check_cpu_traffic(sw_ports, test=False)

    mcast_iface = [m2_if, m3_if, m4_if]
    sw_if2.set_mcast_router(MCAST_ROUTER_PORT.FIXED_ON)
    sw_if2.set_mcast_flood(False)

    result = tl.iperf_mc(m1_if, mcast_iface, mcgrp(1))
    tl.mc_ipref_compare_result(mcast_iface, result, [True, False, False])
    tl.check_cpu_traffic(sw_ports)

    sw_br.set_br_mcast_snooping(False)
    tl._ctl.wait(2)
    result = tl.iperf_mc(m1_if, mcast_iface, mcgrp(1))
    tl.mc_ipref_compare_result(mcast_iface, result, [False, True, True])
    tl.check_cpu_traffic(sw_ports)

    sw_if2.set_mcast_flood(True)
    sw_if2.set_mcast_router(MCAST_ROUTER_PORT.FIXED_OFF)
    sw_if3.set_mcast_router(MCAST_ROUTER_PORT.FIXED_ON)
    sw_if3.set_mcast_flood(False)

    result = tl.iperf_mc(m1_if, mcast_iface, mcgrp(1))
    tl.mc_ipref_compare_result(mcast_iface, result, [True, False, True])
    tl.check_cpu_traffic(sw_ports)

    sw_br.set_br_mcast_snooping()
    tl._ctl.wait(2)

    result = tl.iperf_mc(m1_if, mcast_iface, mcgrp(1))
    tl.mc_ipref_compare_result(mcast_iface, result, [False, True, False])
    tl.check_cpu_traffic(sw_ports)

    sw_if2.set_mcast_router(MCAST_ROUTER_PORT.LEARNING)
    sw_if2.set_mcast_router(MCAST_ROUTER_PORT.LEARNING)
    sw_if3.set_mcast_flood(True)
    for iface in [m1_if, m2_if, m3_if, m4_if]:
        iface.disable_multicast()

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("veth1"),
         ctl.get_host("machine1").get_interface("veth3"),
         ctl.get_host("machine2").get_interface("veth1"),
         ctl.get_host("machine2").get_interface("veth3"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2"),
         ctl.get_host("switch").get_interface("if3"),
         ctl.get_host("switch").get_interface("if4")],
        ctl.get_aliases())
