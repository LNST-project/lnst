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

def do_task(ctl, hosts, ifaces, aliases):
    m1, sw = hosts
    m1_if1, sw_if1 = ifaces

    m1_if1_10 = m1.create_vlan(m1_if1, 10, ip=["192.168.101.10/24",
                                               "2002::1/64"])
    sw_if1_10 = sw.create_vlan(sw_if1, 10, ip=["192.168.101.11/24",
                                               "2002::2/64"])

    sleep(15)

    tl = TestLib(ctl, aliases)
    tl.ping_simple(m1_if1_10, sw_if1_10)
    tl.netperf_tcp(m1_if1_10, sw_if1_10)
    tl.netperf_udp(m1_if1_10, sw_if1_10)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1")],
        ctl.get_aliases())
