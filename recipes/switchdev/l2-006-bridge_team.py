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

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m1_if2, m2_if1, m2_if2, sw_if1, sw_if2, sw_if3, sw_if4 = ifaces

    team_config = '{"runner" : {"name" : "lacp"}}'
    m1_lag1 = m1.create_team(slaves=[m1_if1, m1_if2],
                             config=team_config,
                             ip=["192.168.101.10/24", "2002::1/64"])

    m2_lag1 = m2.create_team(slaves=[m2_if1, m2_if2],
                             config=team_config,
                             ip=["192.168.101.11/24", "2002::2/64"])

    sw_lag1 = sw.create_team(slaves=[sw_if1, sw_if2],
                             config=team_config)

    sw_lag2 = sw.create_team(slaves=[sw_if3, sw_if4],
                             config=team_config)

    sw_br = sw.create_bridge(slaves=[sw_lag1, sw_lag2],
                             options={"vlan_filtering": 1,
                                      "multicast_querier": 1})

    sleep(30)

    tl = TestLib(ctl, aliases)
    tl.ping_simple(m1_lag1, m2_lag1)
    tl.netperf_tcp(m1_lag1, m2_lag1)
    tl.netperf_udp(m1_lag1, m2_lag1)

    sw_lag1.slave_del(sw_if1.get_id())
    sw_lag1.slave_del(sw_if2.get_id())

    m1_lag1.slave_del(m1_if1.get_id())

    # Make sure slowpath is working.
    sw_if1.reset(ip=["192.168.102.10/24", "2003::1/64"])
    m1_if1.reset(ip=["192.168.102.11/24", "2003::2/64"])

    sleep(30)

    tl.ping_simple(sw_if1, m1_if1)

    # Repopulate the LAGs and make sure fastpath is OK.
    sw_if1.set_addresses([])    # LAG port can't have IP address.
    sw_lag3 = sw.create_team(slaves=[sw_if1, sw_if2],
                             config=team_config)
    sw_br.slave_add(sw_lag3.get_id())
    m1_lag1.slave_add(m1_if1.get_id())

    sleep(30)

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
