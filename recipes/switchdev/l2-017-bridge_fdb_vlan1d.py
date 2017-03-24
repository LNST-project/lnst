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

    m1_if1_10 = m1.create_vlan(m1_if1, 10, ip=test_ip(1,1))
    m2_if1_20 = m2.create_vlan(m2_if1, 20, ip=test_ip(1,2))
    sw_if1_10 = sw.create_vlan(sw_if1, 10)
    sw_if2_20 = sw.create_vlan(sw_if2, 20)

    # Ageing time is 10 seconds.
    br_options = {"vlan_filtering": 0, "ageing_time": 1000}
    sw_br = sw.create_bridge(slaves = [sw_if1_10, sw_if2_20], options=br_options)

    sleep(30)

    tl = TestLib(ctl, aliases)
    tl.ping_simple(m1_if1_10, m2_if1_20)
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "software")
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "hardware")

    sleep(20)

    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "software", False)
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "hardware", False)

    # Disable learning and make sure FDB is not populated.
    sw_if1_10.set_br_learning(on=False, self=True)
    tl.ping_simple(m1_if1_10, m2_if1_20)
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "software", False)
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "hardware", False)

    # Disable flooding and make sure ping fails.
    sw_if1_10.set_br_flooding(on=False, self=True)
    tl.ping_simple(m1_if1_10, m2_if1_20, fail_expected=True)

    # Set a static FDB entry and make sure ping works again.
    sw_if1_10.add_br_fdb(str(m1_if1_10.get_hwaddr()), self=True)
    tl.ping_simple(m1_if1_10, m2_if1_20)
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "software", False)
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "hardware")

    # Remove static FDB entry. Ping should fail.
    sw_if1_10.del_br_fdb(str(m1_if1_10.get_hwaddr()), self=True)
    tl.ping_simple(m1_if1_10, m2_if1_20, fail_expected=True)
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "software", False)
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "hardware", False)

    # Enable learning_sync and make sure both FDBs are populated.
    sw_if1_10.set_br_learning(on=True, self=True)
    sw_if1_10.set_br_flooding(on=True, self=True)
    sw_if1_10.set_br_learning_sync(on=True, self=True)
    tl.ping_simple(m1_if1_10, m2_if1_20)
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "software")
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "hardware")

    sleep(20)

    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "software", False)
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "hardware", False)

    # Disable learning_sync and make sure only hardware FDB is populated.
    sw_if1_10.set_br_learning_sync(on=False, self=True)
    tl.ping_simple(m1_if1_10, m2_if1_20)
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "software", False)
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "hardware")

    # Remove port from bridge and add it back. Disable flooding and learning
    # and make sure ping doesn't work. Note that port must be removed from
    # bridge when the FDB entry exists only in the hardware table. Otherwise,
    # bridge code will flush it himself, instead of driver.
    sw_br.slave_del(sw_if1_10.get_id())
    sw_br.slave_add(sw_if1_10.get_id())    # Enables learning sync by default.
    sw_if1_10.set_br_learning(on=False, self=True)
    sw_if1_10.set_br_flooding(on=False, self=True)
    tl.ping_simple(m1_if1_10, m2_if1_20, fail_expected=True)

    # Enable learning and make sure ping works again.
    sw_if1_10.set_br_learning(on=True, self=True)
    tl.ping_simple(m1_if1_10, m2_if1_20)
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "software")
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "hardware")

    sleep(20)

    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "software", False)
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "hardware", False)

    # Insert a static FDB entry and disable learning sync. Ping should work.
    sw_if1_10.add_br_fdb(str(m1_if1_10.get_hwaddr()), self=True)
    sw_if1_10.set_br_learning_sync(on=False, self=True)
    tl.ping_simple(m1_if1_10, m2_if1_20)
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "software", False)
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "hardware")

    sleep(20)

    # Make sure static entry is not aged out.
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "software", False)
    tl.check_fdb(sw_if1_10, m1_if1_10.get_hwaddr(), 0, "hardware")

    # Remove port from bridge and add it back. Disable flooding and learning
    # and make sure ping doesn't work. Note that port must be removed from
    # bridge when the FDB entry exists only in the hardware table. Otherwise,
    # bridge code will flush it himself, instead of driver. Unlike the
    # previous case, here we check if the driver correctly removes the static
    # entry.
    sw_br.slave_del(sw_if1_10.get_id())
    sw_br.slave_add(sw_if1_10.get_id())
    sw_if1_10.set_br_learning(on=False, self=True)
    sw_if1_10.set_br_flooding(on=False, self=True)
    tl.ping_simple(m1_if1_10, m2_if1_20, fail_expected=True)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
