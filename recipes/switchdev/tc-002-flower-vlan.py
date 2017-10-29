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

    m1_if1_85 = m1.create_vlan(m1_if1, 85,
                               ip=["192.168.85.10/24", "2002:85::1/64"])
    m2_if1_85 = m2.create_vlan(m2_if1, 85,
                               ip=["192.168.85.11/24", "2002:85::2/64"])
    m1.run("ip link set dev %s type vlan egress 0:7" % m1_if1_85.get_devname())
    m2.run("ip link set dev %s type vlan egress 0:7" % m2_if1_85.get_devname())

    m1_if1_95 = m1.create_vlan(m1_if1, 95,
                               ip=["192.168.95.10/24", "2002:95::1/64"])
    m2_if1_95 = m2.create_vlan(m2_if1, 95,
                               ip=["192.168.95.11/24", "2002:95::2/64"])

    sw_br1 = sw.create_bridge(slaves=[sw_if1, sw_if2], options={"vlan_filtering": 1,
                                                                "multicast_snooping": 0})
    sw_if1.add_br_vlan(85)
    sw_if2.add_br_vlan(85)
    sw_if1.add_br_vlan(95)
    sw_if2.add_br_vlan(95)

    sleep(15)

    tl = TestLib(ctl, aliases)

    # Test to establish that there is connectivity.
    tl.ping_simple(m1_if1_85, m2_if1_85, count=10, limit_rate=9, interval=0.1)
    tl.ping_simple(m1_if1_95, m2_if1_95, count=10, limit_rate=9, interval=0.1)

    q1 = Qdisc(sw_if1, 0xffff, "ingress")

    # Test that PCP match matches only that PCP.
    q1.flush()
    q1.filter_add("protocol 802.1q flower vlan_prio 7 skip_sw action drop")
    sleep(1)
    tl.ping_simple(m1_if1_85, m2_if1_85, limit_rate=10, fail_expected=True)
    tl.ping_simple(m1_if1_95, m2_if1_95)

    # Test that vlan match actually matches only that vlan.
    q1.flush()
    q1.filter_add("protocol 802.1q flower vlan_id 95 skip_sw action drop")
    sleep(1)
    tl.ping_simple(m1_if1_85, m2_if1_85)
    tl.ping_simple(m1_if1_95, m2_if1_95, limit_rate=10, fail_expected=True)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
