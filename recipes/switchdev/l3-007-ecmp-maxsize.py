"""
Copyright 2016 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
yotamg@mellanox.com (Yotam Gigi)
"""

from lnst.Controller.Task import ctl
from TestLib import TestLib
from time import sleep
import copy
import ecmp_common

MAX_NEXTHOPS = 32

def do_task(ctl, hosts, ifaces, aliases):
    m1, sw, m2 = hosts
    m1_if1, sw_if1, sw_if2, sw_if3, m2_if1, m2_if2, m2_if3, m3_if1 = ifaces

    ecmp_sw_ifaces = [sw_if2, sw_if3]
    ecmp_m_ifaces = [m2_if1, m2_if2]

    m2.config("/proc/sys/net/ipv4/ip_forward", "1")
    m2.config("/proc/sys/net/ipv6/conf/all/forwarding", "1")

    ecmp_common.create_topology(m1_if1, sw_if1, ecmp_sw_ifaces, ecmp_m_ifaces,
                                m2_if3, m3_if1, num_nexthops = MAX_NEXTHOPS)
    sleep(30)

    tl = TestLib(ctl, aliases)
    tl.ping_simple(m1_if1, m3_if1)
    tl.netperf_udp(m1_if1, m3_if1)
    ecmp_common.test_traffic(tl, m1_if1, m3_if1, sw_if1, ecmp_sw_ifaces)

    routes_filter = "to match %s" % m3_if1.get_ip()
    dc_routes, nh_routes = sw.get_routes(routes_filter = routes_filter)
    if len(nh_routes) != 1:
        tl.custom(sw, "route", "could not find the ecmp route")

    for nh in nh_routes[0]["nexthops"]:
        if "offload" not in nh["flags"]:
            tl.custom(sw, "route", "ecmp route is not offloaded")

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("switch"),
              ctl.get_host("machine2")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2"),
         ctl.get_host("switch").get_interface("if3"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if2"),
         ctl.get_host("machine2").get_interface("veth0"),
         ctl.get_host("machine2").get_interface("veth1")],
        ctl.get_aliases())
