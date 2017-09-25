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

def do_task(ctl, hosts, ifaces, host_br, aliases):
    m1, m2, sw = hosts
    m1_if, m2_if, m3_if, m4_if, sw_if1, sw_if2, sw_if3, sw_if4 = ifaces

    sw_ports = [sw_if1, sw_if2, sw_if3, sw_if4]
    sw_br = sw.create_bridge(slaves=sw_ports, options={"vlan_filtering": 1})

    m1_if.set_addresses(test_ip(1, 1))
    m2_if.set_addresses(test_ip(1, 2))
    m3_if.set_addresses(test_ip(1, 3))
    m4_if.set_addresses(test_ip(1, 4))

    tl = TestLib(ctl, aliases)
    mcast_iface = [m1_if, m3_if, m4_if]
    m2_if.enable_multicast()
    for iface in mcast_iface:
        iface.enable_multicast()
    for iface in sw_ports:
        iface.set_mcast_router(MCAST_ROUTER_PORT.FIXED_OFF)

    sw_if1.set_mcast_router(MCAST_ROUTER_PORT.LEARNING)
    sleep(15)

    s_procs = tl.iperf_mc_listen(m3_if, mcgrp(1))
    tl._ctl.wait(2)

    tl.check_cpu_traffic(sw_ports, test=False)
    result = tl.iperf_mc(m2_if, mcast_iface, mcgrp(1))
    tl.mc_ipref_compare_result(mcast_iface, result, [False, True, False])
    tl.check_cpu_traffic(sw_ports)

    result = tl.iperf_mc(m2_if, mcast_iface, mcgrp(2))
    tl.mc_ipref_compare_result(mcast_iface, result, [False, False, False])
    tl.check_cpu_traffic(sw_ports)

    host_br.set_br_mcast_snooping()
    host_br.set_br_mcast_querier(True)
    tl._ctl.wait(30)

    result = tl.iperf_mc(m2_if, mcast_iface, mcgrp(1))
    tl.mc_ipref_compare_result(mcast_iface, result, [True, True, False])
    tl.check_cpu_traffic(sw_ports)

    result = tl.iperf_mc(m2_if, mcast_iface, mcgrp(2))
    tl.mc_ipref_compare_result(mcast_iface, result, [True, False, False])
    tl.check_cpu_traffic(sw_ports)

    for iface in sw_ports:
        iface.set_mcast_router(MCAST_ROUTER_PORT.LEARNING)
    s_procs.intr()

    for iface in mcast_iface:
        iface.disable_multicast()
    m2_if.disable_multicast()

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine1").get_interface("veth3"),
         ctl.get_host("machine2").get_interface("veth1"),
         ctl.get_host("machine2").get_interface("veth3"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2"),
         ctl.get_host("switch").get_interface("if3"),
         ctl.get_host("switch").get_interface("if4")],
        ctl.get_host("machine1").get_interface("brif1"),
        ctl.get_aliases())
