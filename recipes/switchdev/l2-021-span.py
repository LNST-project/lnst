"""
Copyright 2016 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
yotamg@mellanox.com (Yotam Gigi)
"""

from lnst.Controller.Task import ctl
from TestLib import TestLib
from time import sleep
import re
import random

class MirredPort:
    def __init__(self, mirred_port):
        mach = mirred_port.get_host()
        devname = mirred_port.get_devname()
        self.mirred_port = mirred_port
        self.mach = mach

        mach.run("tc qdisc add dev %s clsact" % devname)
        self.pref = [1, 1]

    def create_mirror(self, to_port, ingress = False):
        ingress_str = "ingress" if ingress else "egress"
        from_dev = self.mirred_port.get_devname()
        to_dev = to_port.get_devname()

        self.mach.run("tc filter add dev %s %s pref %d matchall \
                       skip_sw action mirred egress mirror dev %s" % (from_dev,
                       ingress_str, self.pref[ingress], to_dev))
        self.pref[ingress] += 1

    def remove_mirror(self, to_port, ingress = False):
        from_dev = self.mirred_port.get_devname()
        ingress_str = "ingress" if ingress else "egress"
        self.pref[ingress] -= 1
        self.mach.run("tc filter del dev %s pref %d %s" % (from_dev,
                      self.pref[ingress], ingress_str))

def _run_packet_assert(num, main_if, from_addr, to_addr):
    mach = main_if.get_host()

    # filter only icmp/icmpv6 ping, and the reuqested addresses
    filter_str = "(icmp && (icmp[icmptype] == icmp-echo || \
                            icmp[icmptype] == icmp-echoreply) \
                   || (icmp6 && (ip6[40] == 128 || \
                                 ip6[40] == 129))) \
                  && src %s && dst %s" % (from_addr, to_addr)

    packet_assert_mod = ctl.get_module("PacketAssert", options = {
                                       "min" : num, "max" : num,
                                       "promiscuous" : True,
                                       "filter" : filter_str,
                                       "interface" : main_if.get_devname()})
    return mach.run(packet_assert_mod, bg=True)

def run_packet_assert(num, main_if, from_if, to_if, ipv):
    procs = []

    if ipv in ["ipv4", "both"]:
        ipv4_proc = _run_packet_assert(num, main_if, from_if.get_ip(0),
                                       to_if.get_ip(0))
        procs.append(ipv4_proc)

    if ipv in ["ipv6", "both"]:
        ipv6_proc = _run_packet_assert(num, main_if, from_if.get_ip(1),
                                       to_if.get_ip(1))
        procs.append(ipv6_proc)

    return procs

def change_mirror_status(mirror_status, change, mirred_port, to_if):
    mirror_status[change] = not mirror_status[change]
    change_ingress = (change == "ingress")

    to_if.get_host().run("echo " + str(mirror_status))

    if mirror_status[change]:
        mirred_port.create_mirror(to_if, change_ingress)
    else:
        mirred_port.remove_mirror(to_if, change_ingress)

def do_task(ctl, hosts, ifaces, aliases):
    tl = TestLib(ctl, aliases)
    m1, m2, sw = hosts
    m1_if1, m2_if1, m2_if2, sw_if1, sw_if2, sw_if3 = ifaces
    m1.sync_resources(modules=["PacketAssert"])

    # configure interfaces
    m1_if1.reset(ip=["192.168.101.10/24", "2002::1/64"])
    m2_if1.reset(ip=["192.168.101.11/24", "2002::2/64"])
    sw_if3.set_link_up()
    m2_if2.set_link_up()
    sw.create_bridge(slaves=[sw_if1, sw_if2], options={"vlan_filtering": 1,
                                                       "multicast_querier": 1})
    mirred_port = MirredPort(sw_if2)

    sleep(30)

    mirror_status = {"ingress": False, "egress": False }
    for i in range(10):
        change = random.choice(mirror_status.keys())
        change_mirror_status(mirror_status, change, mirred_port, sw_if3)

        in_num = 10 if mirror_status["ingress"] else 0
        out_num = 10 if mirror_status["egress"] else 0

        assert_procs = run_packet_assert(in_num, m2_if2, m2_if1, m1_if1,
                                         aliases["ipv"])
        assert_procs += run_packet_assert(out_num, m2_if2, m1_if1, m2_if1,
                                         aliases["ipv"])
        tl.ping_simple(m1_if1, m2_if1, count=10)
        for assert_proc in assert_procs:
            assert_proc.intr()

    return 0

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if2"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2"),
         ctl.get_host("switch").get_interface("if3")],
        ctl.get_aliases())
