"""
Copyright 2016 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jiri@mellanox.com (Jiri Pirko)
idosch@mellanox.com (Ido Schimmel)
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
    m1_lag1 = m1.create_team(slaves=[m1_if1, m1_if2], config=team_config)

    m2_lag1 = m2.create_team(slaves=[m2_if1, m2_if2], config=team_config)

    sw_lag1 = sw.create_team(slaves=[sw_if1, sw_if2], config=team_config)

    sw_lag2 = sw.create_team(slaves=[sw_if3, sw_if4], config=team_config)

    m1_lag1_10 = m1.create_vlan(m1_lag1, 10, ip=test_ip(1,1))
    m2_lag1_20 = m2.create_vlan(m2_lag1, 20, ip=test_ip(1,2))
    sw_lag1_10 = sw.create_vlan(sw_lag1, 10)
    sw_lag2_20 = sw.create_vlan(sw_lag2, 20)

    # Ageing time is 10 seconds.
    br_options = {"vlan_filtering": 0, "ageing_time": 1000, "multicast_querier": 1}
    sw_br = sw.create_bridge(slaves = [sw_lag1_10, sw_lag2_20], options=br_options)

    sleep(30)

    tl = TestLib(ctl, aliases)
    tl.ping_simple(m1_lag1_10, m2_lag1_20)
    tl.check_fdb(sw_lag1_10, m1_lag1_10.get_hwaddr(), 0, True, True)
    sw_lag1_10.set_br_learning(on=False, master=True)

    sleep(30)

    tl.check_fdb(sw_lag1_10, m1_lag1_10.get_hwaddr(), 0, True, True, False)

    # Make sure FDB is not populated when learning is disabled.
    sw_lag1_10.set_br_learning(on=False, master=True)
    tl.ping_simple(m1_lag1_10, m2_lag1_20)
    tl.check_fdb(sw_lag1_10, m1_lag1_10.get_hwaddr(), 0, True, True, False)

    # Disable flooding and make sure ping fails.
    sw_lag1_10.set_br_flooding(on=False, master=True)
    tl.ping_simple(m1_lag1_10, m2_lag1_20, fail_expected=True)

    # Set a static FDB entry and make sure ping works again. Also check
    # its offloaded
    sw_lag1_10.add_br_fdb(str(m1_lag1_10.get_hwaddr()), master=True)
    tl.ping_simple(m1_lag1_10, m2_lag1_20)
    tl.check_fdb(sw_lag1_10, m1_lag1_10.get_hwaddr(), 0, True, False)

    # Remove static FDB entry. Ping should fail.
    sw_lag1_10.del_br_fdb(str(m1_lag1_10.get_hwaddr()), master=True)
    tl.ping_simple(m1_lag1_10, m2_lag1_20, fail_expected=True)
    tl.check_fdb(sw_lag1_10, m1_lag1_10.get_hwaddr(), 0, True, False, False)

    # Enable learning and flooding and make sure ping works again.
    sw_lag1_10.set_br_learning(on=True, master=True)
    sw_lag1_10.set_br_flooding(on=True, master=True)
    tl.ping_simple(m1_lag1_10, m2_lag1_20)
    tl.check_fdb(sw_lag1_10, m1_lag1_10.get_hwaddr(), 0, True, True)
    sw_lag1_10.set_br_learning(on=False, master=True)

    sleep(30)

    tl.check_fdb(sw_lag1_10, m1_lag1_10.get_hwaddr(), 0, True, True, False)

    # Insert a static FDB entry. Ping should work.
    sw_lag1_10.add_br_fdb(str(m1_lag1_10.get_hwaddr()), master=True)
    tl.ping_simple(m1_lag1_10, m2_lag1_20)
    tl.check_fdb(sw_lag1_10, m1_lag1_10.get_hwaddr(), 0, True, False)

    sleep(30)

    # Make sure static entry is not aged out.
    tl.check_fdb(sw_lag1_10, m1_lag1_10.get_hwaddr(), 0, True, False)

    # Remove port from bridge and add it back. The static entry added
    # before should be flushed. Disable flooding and learning and make
    # sure ping doesn't work.
    sw_br.slave_del(sw_lag1_10.get_id())
    sw_br.slave_add(sw_lag1_10.get_id())
    sw_lag1_10.set_br_learning(on=False, master=True)
    sw_lag1_10.set_br_flooding(on=False, master=True)
    tl.ping_simple(m1_lag1_10, m2_lag1_20, fail_expected=True)

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
