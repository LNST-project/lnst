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

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m1_if2, m2_if1, m2_if2, sw_if1, sw_if2, sw_if3, sw_if4 = ifaces

    team_config = '{"runner" : {"name" : "lacp"}}'
    m1_lag1 = m1.create_team(slaves=[m1_if1, m1_if2], config=team_config,
                             ip=["192.168.101.10/24", "2002::1/64"])

    m2_lag1 = m2.create_team(slaves=[m2_if1, m2_if2], config=team_config,
                             ip=["192.168.101.11/24", "2002::2/64"])

    sw_lag1 = sw.create_team(slaves=[sw_if1, sw_if2], config=team_config)

    sw_lag2 = sw.create_team(slaves=[sw_if3, sw_if4], config=team_config)

    # Ageing time is 10 seconds.
    br_options = {"vlan_filtering": 1, "ageing_time": 1000}
    sw_br = sw.create_bridge(slaves = [sw_lag1, sw_lag2], options=br_options)

    sleep(15)

    tl = TestLib(ctl, aliases)
    tl.ping_simple(m1_lag1, m2_lag1)
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "software")
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "hardware")

    sleep(20)

    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "software", False)
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "hardware", False)

    # Disable learning and make sure FDB is not populated.
    sw_lag1.set_br_learning(on=False, self=True)
    tl.ping_simple(m1_lag1, m2_lag1)
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "software", False)
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "hardware", False)

    # Disable flooding and make sure ping fails.
    sw_lag1.set_br_flooding(on=False, self=True)
    tl.ping_simple(m1_lag1, m2_lag1, fail_expected=True)

    # Set a static FDB entry and make sure ping works again.
    sw_lag1.add_br_fdb(str(m1_lag1.get_hwaddr()), self=True, vlan_tci=1)
    tl.ping_simple(m1_lag1, m2_lag1)
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "software", False)
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "hardware")

    # Remove static FDB entry. Ping should fail.
    sw_lag1.del_br_fdb(str(m1_lag1.get_hwaddr()), self=True, vlan_tci=1)
    tl.ping_simple(m1_lag1, m2_lag1, fail_expected=True)
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "software", False)
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "hardware", False)

    # Enable learning_sync and make sure both FDBs are populated.
    sw_lag1.set_br_learning(on=True, self=True)
    sw_lag1.set_br_flooding(on=True, self=True)
    sw_lag1.set_br_learning_sync(on=True, self=True)
    tl.ping_simple(m1_lag1, m2_lag1)
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "software")
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "hardware")

    sleep(20)

    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "software", False)
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "hardware", False)

    # Disable learning_sync and make sure only hardware FDB is populated.
    sw_lag1.set_br_learning_sync(on=False, self=True)
    tl.ping_simple(m1_lag1, m2_lag1)
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "software", False)
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "hardware")

    # Remove port from bridge and add it back. Disable flooding and learning
    # and make sure ping doesn't work. Note that port must be removed from
    # bridge when the FDB entry exists only in the hardware table. Otherwise,
    # bridge code will flush it himself, instead of driver.
    sw_br.slave_del(sw_lag1.get_id())
    sw_br.slave_add(sw_lag1.get_id())    # Enables learning sync by default.
    sw_lag1.set_br_learning(on=False, self=True)
    sw_lag1.set_br_flooding(on=False, self=True)
    tl.ping_simple(m1_lag1, m2_lag1, fail_expected=True)

    # Enable learning and make sure ping works again.
    sw_lag1.set_br_learning(on=True, self=True)
    tl.ping_simple(m1_lag1, m2_lag1)
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "software")
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "hardware")

    sleep(20)

    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "software", False)
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "hardware", False)

    # Insert a static FDB entry and disable learning sync. Ping should work.
    sw_lag1.add_br_fdb(str(m1_lag1.get_hwaddr()), self=True, vlan_tci=1)
    sw_lag1.set_br_learning_sync(on=False, self=True)
    tl.ping_simple(m1_lag1, m2_lag1)
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "software", False)
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "hardware")

    sleep(20)

    # Make sure static entry is not aged out.
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "software", False)
    tl.check_fdb(sw_lag1, m1_lag1.get_hwaddr(), 1, "hardware")

    # Remove port from bridge and add it back. Disable flooding and learning
    # and make sure ping doesn't work. Note that port must be removed from
    # bridge when the FDB entry exists only in the hardware table. Otherwise,
    # bridge code will flush it himself, instead of driver. Unlike the
    # previous case, here we check if the driver correctly removes the static
    # entry.
    sw_br.slave_del(sw_lag1.get_id())
    sw_br.slave_add(sw_lag1.get_id())
    sw_lag1.set_br_learning(on=False, self=True)
    sw_lag1.set_br_flooding(on=False, self=True)
    tl.ping_simple(m1_lag1, m2_lag1, fail_expected=True)

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
