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
    m1_if1, m1_if2, m2_if1, m2_if2, sw_if1, sw_if2, sw_if3, sw_if4 = ifaces

    team_config = '{"runner" : {"name" : "lacp"}}'
    m1_lag1 = m1.create_team(slaves=[m1_if1, m1_if2],
                             config=team_config, ip=test_ip(1, 1))
    m1_lag1_10 = m1.create_vlan(m1_lag1, 10, ip=test_ip(2, 1))
    m1_lag1_20 = m1.create_vlan(m1_lag1, 20, ip=test_ip(3, 1))

    m2_lag1 = m2.create_team(slaves=[m2_if1, m2_if2],
                             config=team_config, ip=test_ip(1, 2))
    m2_lag1_10 = m2.create_vlan(m2_lag1, 10, ip=test_ip(2, 2))
    m2_lag1_21 = m2.create_vlan(m2_lag1, 21, ip=test_ip(3, 2))

    sw_lag1 = sw.create_team(slaves=[sw_if1, sw_if2], config=team_config)
    sw_lag2 = sw.create_team(slaves=[sw_if3, sw_if4], config=team_config)
    br_options = {"vlan_filtering": 1, "multicast_querier": 1}
    sw_br1 = sw.create_bridge(slaves=[sw_lag1, sw_lag2], options=br_options)

    sw_lag1_10 = sw.create_vlan(sw_lag1, 10)
    sw_lag2_10 = sw.create_vlan(sw_lag2, 10)
    sw_br2 = sw.create_bridge(slaves=[sw_lag1_10, sw_lag2_10],
                              options={"multicast_querier": 1})

    sw_lag1_20 = sw.create_vlan(sw_lag1, 20)
    sw_lag2_21 = sw.create_vlan(sw_lag2, 21)
    sw_br3 = sw.create_bridge(slaves=[sw_lag1_20, sw_lag2_21],
                              options={"multicast_querier": 1})

    sleep(30)

    tl = TestLib(ctl, aliases)

    tl.ping_simple(m1_lag1, m2_lag1)
    tl.netperf_tcp(m1_lag1, m2_lag1)
    tl.netperf_udp(m1_lag1, m2_lag1)

    tl.ping_simple(m1_lag1_10, m2_lag1_10)
    tl.netperf_tcp(m1_lag1_10, m2_lag1_10)
    tl.netperf_udp(m1_lag1_10, m2_lag1_10)

    tl.ping_simple(m1_lag1_20, m2_lag1_21)
    tl.netperf_tcp(m1_lag1_20, m2_lag1_21)
    tl.netperf_udp(m1_lag1_20, m2_lag1_21)

    sw_lag1.slave_del(sw_if1.get_id())
    sw_lag1.slave_del(sw_if2.get_id())

    m1_lag1.slave_del(m1_if1.get_id())

    # Make sure slowpath is working.
    sw_if1.reset(ip=test_ip(4, 1))
    m1_if1.reset(ip=test_ip(4, 2))

    sleep(30)

    tl.ping_simple(sw_if1, m1_if1)

    # Repopulate the LAGs and make sure fastpath is OK.
    sw_if1.set_addresses([])    # LAG port can't have IP address.
    sw_lag3 = sw.create_team(slaves=[sw_if1, sw_if2],
                             config=team_config)
    sw_br1.slave_add(sw_lag3.get_id())

    sw_lag3_10 = sw.create_vlan(sw_lag3, 10)
    sw_br2.slave_add(sw_lag3_10.get_id())

    sw_lag3_20 = sw.create_vlan(sw_lag3, 20)
    sw_br3.slave_add(sw_lag3_20.get_id())

    m1_lag1.slave_add(m1_if1.get_id())

    sleep(30)

    tl.ping_simple(m1_lag1, m2_lag1)
    tl.netperf_tcp(m1_lag1, m2_lag1)
    tl.netperf_udp(m1_lag1, m2_lag1)

    tl.ping_simple(m1_lag1_10, m2_lag1_10)
    tl.netperf_tcp(m1_lag1_10, m2_lag1_10)
    tl.netperf_udp(m1_lag1_10, m2_lag1_10)

    tl.ping_simple(m1_lag1_20, m2_lag1_21)
    tl.netperf_tcp(m1_lag1_20, m2_lag1_21)
    tl.netperf_udp(m1_lag1_20, m2_lag1_21)

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
