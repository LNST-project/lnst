"""
Copyright 2016 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
eladr@mellanox.com (Elad Raz)
jiri@mellanox.com (Jiri Pirko)
nogahf@mellanox.com (Nogah Frankel)
"""

from lnst.Controller.Task import ctl
from TestLib import TestLib
from time import sleep

def test_ip(major, minor):
    return ["192.168.10%d.%d/24" % (major, minor),
            "2002:%d::%d/64" % (major, minor)]

def mcgrp(i):
    return "239.255.1.%d" % i

def test_standard_mutlicast(tl, sender, listeners, bridged, group):
    s_procs = [tl.iperf_mc_listen(listener, group) for listener in listeners]
    res = tl.iperf_mc(sender,  listeners+ bridged, group)
    expected = [True for l in listeners] + [False for l in bridged]
    tl.mc_ipref_compare_result(listeners + bridged, res, expected)
    map(lambda i:i.intr(), s_procs)

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if, m2_if, m3_if, m4_if, sw_if1, sw_if2, sw_if3, sw_if4 = ifaces

    # Create a bridge
    sw_ports = [sw_if1, sw_if2, sw_if3, sw_if4]
    sw_br = sw.create_bridge(slaves=sw_ports, options={"vlan_filtering": 1,
                                                       "multicast_querier": 1})

    m1_if.set_addresses(test_ip(1,1))
    m2_if.set_addresses(test_ip(1, 2))
    m3_if.set_addresses(test_ip(1, 3))
    m4_if.set_addresses(test_ip(1, 4))
    sleep(30)

    tl = TestLib(ctl, aliases)

    tl.check_cpu_traffic(sw_ports, test=False)
    for iface in [m1_if, m2_if, m3_if, m4_if]:
        iface.enable_multicast()

    test_standard_mutlicast(tl, m1_if, [m2_if, m4_if], [m3_if], mcgrp(3))
    test_standard_mutlicast(tl, m1_if, [m4_if], [m2_if, m3_if], mcgrp(4))
    test_standard_mutlicast(tl, m2_if, [m3_if, m4_if, m1_if], [], mcgrp(5))
    for iface in [m1_if, m2_if, m3_if, m4_if]:
        iface.disable_multicast()
    tl.check_cpu_traffic(sw_ports)

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
