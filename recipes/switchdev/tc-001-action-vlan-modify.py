"""
Copyright 2017 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
petrm@mellanox.com (Petr Machata)
"""

from lnst.Controller.Task import ctl
from TestLib import TestLib, Qdisc
from time import sleep

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m2_if1, sw_if1, sw_if2 = ifaces

    m1_if1_85 = m1.create_vlan(m1_if1, 85, ip=["192.168.101.10/24", "2002::1/64"])
    m2_if1_65 = m2.create_vlan(m2_if1, 65, ip=["192.168.101.11/24", "2002::2/64"])

    sw_br1 = sw.create_bridge(slaves=[sw_if1, sw_if2], options={"vlan_filtering": 1,
                                                                "multicast_snooping": 0})
    sw_if1.add_br_vlan(85)
    sw_if2.add_br_vlan(65)

    q1 = Qdisc(sw_if1, 0xffff, "ingress")
    q1.filter_add("protocol all flower skip_sw action vlan modify id 65")

    q2 = Qdisc(sw_if2, 0xffff, "ingress")
    q2.filter_add("protocol all flower skip_sw action vlan modify id 85")

    sleep(10)

    tl = TestLib(ctl, aliases)
    tl.ping_simple(m1_if1_85, m2_if1_65)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
