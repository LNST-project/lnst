"""
Copyright 2016 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jiri@mellanox.com (Jiri Pirko)
"""

from lnst.Controller.Task import ctl
from TestLib import TestLib
from time import sleep

def test_ip(major, minor):
    return ["192.168.10%d.%d/24" % (major, minor),
            "2002:%d::%d/64" % (major, minor)]

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m2_if1, sw_if1, sw_if2 = ifaces

    m1_if1.reset(ip=test_ip(1, 1))

    m1_if1_10 = m1.create_vlan(m1_if1, 10, ip=test_ip(2, 1))
    m1_if1_20 = m1.create_vlan(m1_if1, 20, ip=test_ip(3, 1))

    m2_if1.reset(ip=test_ip(1, 2))
    m2_if1_10 = m2.create_vlan(m2_if1, 10, ip=test_ip(2, 2))
    m2_if1_20 = m2.create_vlan(m2_if1, 20, ip=test_ip(3, 2))

    br_options = {"vlan_filtering": 1, "multicast_snooping": 0}
    sw.create_bridge(slaves=[sw_if1, sw_if2], options=br_options)

    sw_if1.add_br_vlan(10)
    sw_if2.add_br_vlan(10)
    sw_if1.add_br_vlan(20)
    sw_if2.add_br_vlan(20)

    sleep(30)

    tl = TestLib(ctl, aliases)

    tl.ping_simple(m1_if1, m2_if1)
    tl.netperf_tcp(m1_if1, m2_if1)
    tl.netperf_udp(m1_if1, m2_if1)

    tl.ping_simple(m1_if1_10, m2_if1_10)
    tl.netperf_tcp(m1_if1_10, m2_if1_10)
    tl.netperf_udp(m1_if1_10, m2_if1_10)

    tl.ping_simple(m1_if1_20, m2_if1_20)
    tl.netperf_tcp(m1_if1_20, m2_if1_20)
    tl.netperf_udp(m1_if1_20, m2_if1_20)

    sw_if1.add_br_vlan(500, pvid=True, untagged=True)
    sw_if2.add_br_vlan(500, pvid=True, untagged=True)
    sleep(1)
    tl.ping_simple(m1_if1, m2_if1)
    tl.netperf_tcp(m1_if1, m2_if1)
    tl.netperf_udp(m1_if1, m2_if1)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
