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
    m1_if1, m2_if1, sw_if1, sw_if2 = ifaces

    m1_if1.reset(ip=test_ip(1,1))
    m2_if1.reset(ip=test_ip(1,2))

    # Ageing time is 10 seconds.
    br_options = {"vlan_filtering": 1, "ageing_time": 1000,
                  "multicast_querier": 1}
    sw_br = sw.create_bridge(slaves = [sw_if1, sw_if2], options=br_options)

    sleep(30)

    tl = TestLib(ctl, aliases)
    tl.ping_simple(m1_if1, m2_if1)
    tl.check_fdb(sw_if1, m1_if1.get_hwaddr(), 1, True, True)
    sw_if1.set_br_learning(on=False, master=True)

    sleep(30)

    tl.check_fdb(sw_if1, m1_if1.get_hwaddr(), 1, True, True, False)

    # Make sure FDB is not populated when learning is disabled.
    sw_if1.set_br_learning(on=False, master=True)
    tl.ping_simple(m1_if1, m2_if1)
    tl.check_fdb(sw_if1, m1_if1.get_hwaddr(), 1, True, True, False)

    # Disable flooding and make sure ping fails.
    sw_if1.set_br_flooding(on=False, master=True)
    tl.ping_simple(m1_if1, m2_if1, fail_expected=True)

    # Set a static FDB entry and make sure ping works again. Also check
    # its offloaded
    sw_if1.add_br_fdb(str(m1_if1.get_hwaddr()), master=True, vlan_tci=1)
    tl.ping_simple(m1_if1, m2_if1)
    tl.check_fdb(sw_if1, m1_if1.get_hwaddr(), 1, True, False)

    # Remove static FDB entry. Ping should fail.
    sw_if1.del_br_fdb(str(m1_if1.get_hwaddr()), master=True, vlan_tci=1)
    tl.ping_simple(m1_if1, m2_if1, fail_expected=True)
    tl.check_fdb(sw_if1, m1_if1.get_hwaddr(), 1, True, False, False)

    # Enable learning and flooding and make sure ping works again.
    sw_if1.set_br_learning(on=True, master=True)
    sw_if1.set_br_flooding(on=True, master=True)
    tl.ping_simple(m1_if1, m2_if1)
    tl.check_fdb(sw_if1, m1_if1.get_hwaddr(), 1, True, True)
    sw_if1.set_br_learning(on=False, master=True)

    sleep(20)

    tl.check_fdb(sw_if1, m1_if1.get_hwaddr(), 1, True, True, False)

    # Insert a static FDB entry. Ping should work.
    sw_if1.add_br_fdb(str(m1_if1.get_hwaddr()), master=True, vlan_tci=1)
    tl.ping_simple(m1_if1, m2_if1)
    tl.check_fdb(sw_if1, m1_if1.get_hwaddr(), 1, True, False)

    sleep(20)

    # Make sure static entry is not aged out.
    tl.check_fdb(sw_if1, m1_if1.get_hwaddr(), 1, True, False)

    # Remove port from bridge and add it back. The static entry added
    # before should be flushed. Disable flooding and learning and make
    # sure ping doesn't work.
    sw_br.slave_del(sw_if1.get_id())
    sw_br.slave_add(sw_if1.get_id())
    sw_if1.set_br_learning(on=False, master=True)
    sw_if1.set_br_flooding(on=False, master=True)
    tl.ping_simple(m1_if1, m2_if1, fail_expected=True)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
