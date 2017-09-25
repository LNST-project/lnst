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
from lnst.Common.Consts import MCAST_ROUTER_PORT

def test_ip(major, minor):
    return ["192.168.10%d.%d/24" % (major, minor),
            "2002:%d::%d/64" % (major, minor)]

def mcgrp(i):
    return "239.255.1.%d" % i

def set_peer_mc_router(dev_map, dev, value):
    sw_dev = dev_map[dev]
    sw_dev.set_mcast_router(value)
    sw = sw_dev.get_host()

def test_mrouter(tl, dev_map, sender, listeners, bridged, mc_routers, group):
    mcast_ifaces = listeners + bridged

    expected_no_mcr = [True for l in listeners] + [False for l in bridged]
    expected = [True for l in listeners] + [l in mc_routers for l in bridged]

    s_procs = [tl.iperf_mc_listen(listener, group) for listener in listeners]
    tl._ctl.wait(2)

    result = tl.iperf_mc(sender,  mcast_ifaces, group)
    tl.mc_ipref_compare_result(mcast_ifaces, result, expected_no_mcr)

    for mcr in mc_routers:
        set_peer_mc_router(dev_map, mcr, MCAST_ROUTER_PORT.FIXED_ON)

    result = tl.iperf_mc(sender, mcast_ifaces, group)
    tl.mc_ipref_compare_result(mcast_ifaces, result, expected)

    for mcr in mc_routers:
        set_peer_mc_router(dev_map, mcr, MCAST_ROUTER_PORT.LEARNING)

    result = tl.iperf_mc(sender,  mcast_ifaces, group)
    tl.mc_ipref_compare_result(mcast_ifaces, result, expected_no_mcr)

    for mcr in mc_routers:
        set_peer_mc_router(dev_map, mcr, MCAST_ROUTER_PORT.FIXED_ON)

    result = tl.iperf_mc(sender, mcast_ifaces, group)
    tl.mc_ipref_compare_result(mcast_ifaces, result, expected)

    for proc in s_procs:
        proc.intr()

    for mcr in mc_routers:
        set_peer_mc_router(dev_map, mcr, MCAST_ROUTER_PORT.LEARNING)

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if, m2_if, m3_if, m4_if, sw_if1, sw_if2, sw_if3, sw_if4 = ifaces
    dev_map = { m1_if : sw_if1, m2_if : sw_if2, m3_if : sw_if3, m4_if : sw_if4 }

    # Create a bridge
    sw_ifaces = [sw_if1, sw_if2, sw_if3, sw_if4]
    sw_br = sw.create_bridge(slaves=sw_ifaces, options={"vlan_filtering": 1})

    m1_if.set_addresses(test_ip(1, 1))
    m2_if.set_addresses(test_ip(1, 2))
    m3_if.set_addresses(test_ip(1, 3))
    m4_if.set_addresses(test_ip(1, 4))
    sleep(15)

    tl = TestLib(ctl, aliases)

    for iface in [m1_if, m2_if, m3_if, m4_if]:
        iface.enable_multicast()

    tl.check_cpu_traffic(sw_ifaces, test=False)
    test_mrouter(tl, dev_map,                   \
            sender = m1_if,                     \
            listeners = [],                     \
            bridged = [m3_if, m2_if, m4_if],    \
            mc_routers = [m4_if],               \
            group = mcgrp(1))

    test_mrouter(tl, dev_map,                   \
            sender = m1_if,                     \
            listeners = [m2_if],                \
            bridged = [m4_if, m3_if],           \
            mc_routers = [m3_if],               \
            group = mcgrp(2))

    test_mrouter(tl, dev_map,                   \
            sender = m1_if,                     \
            listeners = [m2_if, m4_if],         \
            bridged = [m3_if],                  \
            mc_routers = [m3_if],               \
            group = mcgrp(3))

    test_mrouter(tl, dev_map,                   \
            sender = m1_if,                     \
            listeners = [m2_if],                \
            bridged = [m3_if, m4_if],           \
            mc_routers = [m3_if, m4_if],        \
            group = mcgrp(4))

    test_mrouter(tl, dev_map,                   \
            sender = m1_if,                     \
            listeners = [m2_if, m4_if],         \
            bridged = [m3_if],                  \
            mc_routers = [m2_if],               \
            group = mcgrp(5))

    test_mrouter(tl, dev_map,                   \
            sender = m1_if,                     \
            listeners = [m2_if, m4_if],         \
            bridged = [m3_if],                  \
            mc_routers = [m2_if, m3_if],        \
            group = mcgrp(6))

    tl.check_cpu_traffic(sw_ifaces)
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
