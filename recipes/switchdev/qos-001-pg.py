"""
Copyright 2016 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
idosch@mellanox.com (Ido Schimmel)
"""

from lnst.Controller.Task import ctl
from TestLib import TestLib
from time import sleep

def check_itc_max_occ(tl, iface, itc):
    err_msg = ""

    for itc_iter in range(1, 8):
        max_occ = tl.devlink_tc_max_occ_get(iface, True, itc_iter)
        if max_occ != 0 and itc != itc_iter:
            err_msg = "itc {0} occ isn't zero when should be".format(itc_iter)
            break
        elif max_occ == 0 and itc == itc_iter:
            err_msg = "itc {0} occ is zero when shouldn't be".format(itc)
            break

    tl.custom(iface.get_host(), "itc occ test", err_msg)

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m2_if1, sw_if1, sw_if2 = ifaces

    m1_if1.reset(ip=["192.168.101.10/24", "2002::1/64"])
    m2_if1.reset(ip=["192.168.101.11/24", "2002::2/64"])

    sleep(30)

    sw.create_bridge(slaves=[sw_if1, sw_if2], options={"vlan_filtering": 1})
    sw_if1.add_br_vlan(10)
    sw_if2.add_br_vlan(10)

    tl = TestLib(ctl, aliases)

    sw.enable_service("lldpad")
    sw_if1.enable_lldp()
    tl.lldp_ets_default_set(sw_if1, willing=False)

    m1.enable_service("lldpad")
    m1_if1.enable_lldp()
    tl.lldp_ets_default_set(m1_if1)

    tl.ping_simple(m1_if1, m2_if1)

    for prio in range(1, 8):
        tl.lldp_ets_up2tc_set(sw_if1, [(prio, prio)])
        tl.devlink_clearmax(sw, sw_if1.get_devlink_name())

        sleep(5)    # lldpad's event loop runs every second.
        tl.pktgen(m1_if1, m2_if1, m1_if1.get_mtu(), vlan_id=10, vlan_p=prio)
        check_itc_max_occ(tl, sw_if1, prio)

        tl.lldp_ets_up2tc_set(sw_if1, [(prio, 0)])

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
