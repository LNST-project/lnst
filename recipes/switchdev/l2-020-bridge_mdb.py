"""
Copyright 2016 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
eladr@mellanox.com (Elad Raz)
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
    m1_if, m2_if, m3_if, m4_if, sw_if1, sw_if2, sw_if3, sw_if4 = ifaces

    # Create a bridge
    sw_br = sw.create_bridge(slaves=[sw_if1, sw_if2, sw_if3, sw_if4],
        options={"vlan_filtering": 1})

    m1_if.set_addresses(["192.168.101.10/24", "2002::1/64"])
    m2_if.set_addresses(["192.168.101.11/24", "2002::2/64"])
    m3_if.set_addresses(["192.168.101.13/24", "2002::3/64"])
    m4_if.set_addresses(["192.168.101.14/24", "2002::4/64"])
    sleep(30)

    tl = TestLib(ctl, aliases)
    tl.iperf_mc(m1_if, [m2_if, m4_if], [m3_if], "239.255.1.3")
    tl.iperf_mc(m1_if, [m4_if], [], "239.255.1.4")
    tl.iperf_mc(m2_if, [m3_if, m4_if, m1_if] , [], "239.255.1.5")

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("veth1"),
         ctl.get_host("machine1").get_interface("veth3"),
         ctl.get_host("machine2").get_interface("veth1"),
         ctl.get_host("machine2").get_interface("veth3"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2"),
         ctl.get_host("switch").get_interface("if3"),
         ctl.get_host("switch").get_interface("if4")],
        ctl.get_aliases())
