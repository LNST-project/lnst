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

    # We can't set STP state if kernel's STP is running.
    br_options = {"stp_state": 0, "vlan_filtering": 1, "ageing_time": 1000,
                  "multicast_querier": 1}
    sw.create_bridge(slaves=[sw_if1, sw_if2], options=br_options)

    m1_if1.reset(ip=test_ip(1, 1))
    m2_if1.reset(ip=test_ip(1, 2))

    sleep(40)

    tl = TestLib(ctl, aliases)

    # Set STP state to DISABLED and make sure ping fails and FDB is not
    # populated.
    sw_if1.set_br_state(0)
    tl.ping_simple(m1_if1, m2_if1, fail_expected=True)
    tl.check_fdb(sw_if1, m1_if1.get_hwaddr(), 1, True, True, False)

    # Set STP state to LISTENING and make sure ping fails and FDB is not
    # populated.
    sw_if1.set_br_state(1)
    tl.ping_simple(m1_if1, m2_if1, fail_expected=True)
    tl.check_fdb(sw_if1, m1_if1.get_hwaddr(), 1, True, True, False)

    # Set STP state to LEARNING and make sure ping fails, but FDB *is*
    # populated.
    sw_if1.set_br_state(2)
    tl.ping_simple(m1_if1, m2_if1, fail_expected=True)
    tl.check_fdb(sw_if1, m1_if1.get_hwaddr(), 1, True, True)

    sleep(30)

    tl.check_fdb(sw_if1, m1_if1.get_hwaddr(), 1, True, True, False)

    # Set STP state to FORWARDING and make sure ping works and FDB is
    # populated.
    sw_if1.set_br_state(3)
    tl.ping_simple(m1_if1, m2_if1)
    tl.check_fdb(sw_if1, m1_if1.get_hwaddr(), 1, True, True)

    sleep(30)

    tl.check_fdb(sw_if1, m1_if1.get_hwaddr(), 1, True, True, False)

    # Make sure that even with a static FDB record we don't get traffic
    # when state is DISABLED, LEARNING or LISTENING.
    sw_if2.add_br_fdb(str(m2_if1.get_hwaddr()), master=True, vlan_tci=1)
    sw_if1.set_br_state(0)
    tl.ping_simple(m1_if1, m2_if1, fail_expected=True)
    sw_if1.set_br_state(1)
    tl.ping_simple(m1_if1, m2_if1, fail_expected=True)
    sw_if1.set_br_state(2)
    tl.ping_simple(m1_if1, m2_if1, fail_expected=True)

    # Cleanup
    sw_if2.del_br_fdb(str(m2_if1.get_hwaddr()), master=True, vlan_tci=1)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
