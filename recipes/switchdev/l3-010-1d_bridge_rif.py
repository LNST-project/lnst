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

ROUTES_COUNT = 5000
PKTGEN_COUNT = 10000

MAJOR_MIN = 10
MINOR_MIN = 1
MINOR_MAX = 254
MINORS_TOTAL = MINOR_MAX - MINOR_MIN + 1

def test_ip(major, minor, prefix=[24,64]):
    return ["192.168.1%d.%d%s" % (major, minor,
            "/" + str(prefix[0]) if len(prefix) > 0 else ""),
            "2002:%d::%d%s" % (major, minor,
            "/" + str(prefix[1]) if len(prefix) > 1 else "")]

def ipv4(test_ip):
    return test_ip[0]

def ipv6(test_ip):
    return test_ip[1]

def do_task(ctl, hosts, ifaces, aliases):
    """
    Create the following topology:

	   M1
    +--------------+
    |              |
    |              |                   SWITCH
    |  ip(1, 1).10 +---+     +-----------------------+
    |              |   |     |                       |
    |              |   |     | .1d bridge            |
    +--------------+   +-----+---+                   |
			     |   |                   |
	   M2                |   |                   |
    +--------------+         |   +---+ ip(1, 10).10  |
    |              |         |   |                   |
    |              |         |   |                   |
    |  ip(1, 2).10 +---------+---+                   |
    |              |         |                       |
    |              |         |                       |
    +--------------+         |                       |
			     |                       |
	   M3                |                       |
    +--------------+   +-----+-------+ ip(2, 11)     |
    |              |   |     |                       |
    |              |   |     |                       |
    |     ip(2, 3) +---+     +-----------------------+
    |              |
    |              |
    +--------------+

    And test that:
     - The bridge does forward packets between M1 and M2
     - The packets does get routed from M3 to M1 and M2
     - Packets directed to ip(1, 10) (the bridge device) does get to the machine
    """
    m1, sw, m2 = hosts
    m1_if1, m3_if1, sw_if1, sw_if2, sw_if3, m2_if1 = ifaces

    sw_if1_v10 = sw.create_vlan(sw_if1, 10)
    sw_if3_v10 = sw.create_vlan(sw_if3, 10)
    sw_br = sw.create_bridge(slaves=[sw_if1_v10, sw_if3_v10],
                             options={"vlan_filtering": 0})
    sw_br.set_addresses(ips=test_ip(1, 10))

    m1_if1_v10 = m1.create_vlan(m1_if1, 10, ip=test_ip(1, 1))
    m2_if1_v10 = m2.create_vlan(m2_if1, 10, ip=test_ip(1, 2))

    sw_if2.set_addresses(ips=test_ip(2, 10))
    m3_if1.set_addresses(ips=test_ip(2, 3))

    m1_if1.add_nhs_route(ipv4(test_ip(2, 0)), [str(sw_br.get_ip(0))])
    m2_if1.add_nhs_route(ipv4(test_ip(2, 0)), [str(sw_br.get_ip(0))])
    m3_if1.add_nhs_route(ipv4(test_ip(1, 0)), [str(sw_if2.get_ip(0))])

    m1_if1.add_nhs_route(ipv6(test_ip(2, 0)), [str(sw_br.get_ip(1))])
    m2_if1.add_nhs_route(ipv6(test_ip(2, 0)), [str(sw_br.get_ip(1))])
    m3_if1.add_nhs_route(ipv6(test_ip(1, 0)), [str(sw_if2.get_ip(1))])

    sleep(30)
    tl = TestLib(ctl, aliases)
    tl.ping_simple(m2_if1_v10, m1_if1_v10)
    tl.ping_simple(m2_if1_v10, sw_br)
    tl.ping_simple(m1_if1_v10, m3_if1)
    tl.ping_simple(m2_if1_v10, m3_if1)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("switch"),
              ctl.get_host("machine2")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine1").get_interface("if2"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2"),
         ctl.get_host("switch").get_interface("if3"),
         ctl.get_host("machine2").get_interface("if1")],
        ctl.get_aliases())
