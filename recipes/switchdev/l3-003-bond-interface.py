"""
Copyright 2016 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
eladr@mellanox.com (Elad Raz)
"""

from lnst.Controller.Task import ctl
from TestLib import TestLib
from time import sleep

def test_ip(major, minor, prefix=[24,64]):
    return ["192.168.10%d.%d%s" % (major, minor,
            "/" + str(prefix[0]) if len(prefix) > 0 else ""),
            "2002:%d::%d%s" % (major, minor,
            "/" + str(prefix[1]) if len(prefix) > 1 else "")]

def ipv4(test_ip):
    return test_ip[0]

def ipv6(test_ip):
    return test_ip[1]

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m1_if2, m2_if1, m2_if2, sw_if1, sw_if2, sw_if3, sw_if4 = ifaces

    bond_options = {"mode": "802.3ad", "miimon": "100"}
    m1_lag1 = m1.create_bond(slaves=[m1_if1, m1_if2], options=bond_options,
                             ip=test_ip(1,1))
    m2_lag1 = m2.create_bond(slaves=[m2_if1, m2_if2], options=bond_options,
                             ip=test_ip(2,1))

    m1_lag1.add_nhs_route(ipv4(test_ip(2,0)), [ipv4(test_ip(1,2,[]))]);
    m2_lag1.add_nhs_route(ipv4(test_ip(1,0)), [ipv4(test_ip(2,2,[]))]);

    m1_if1.add_nhs_route(ipv6(test_ip(2,0)), [ipv6(test_ip(1,2,[]))], ipv6=True);
    m2_if1.add_nhs_route(ipv6(test_ip(1,0)), [ipv6(test_ip(2,2,[]))], ipv6=True);

    sw_lag1 = sw.create_bond(slaves=[sw_if1, sw_if2], options=bond_options,
                             ip=test_ip(1,2))
    sw_lag2 = sw.create_bond(slaves=[sw_if3, sw_if4], options=bond_options,
                             ip=test_ip(2,2))

    sleep(30)

    tl = TestLib(ctl, aliases)
    tl.ping_simple(m1_lag1, m2_lag1)
    tl.netperf_tcp(m1_lag1, m2_lag1)
    tl.netperf_udp(m1_lag1, m2_lag1)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine1").get_interface("if2"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if2"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2"),
         ctl.get_host("switch").get_interface("if3"),
         ctl.get_host("switch").get_interface("if4")],
        ctl.get_aliases())
