"""
Copyright 2016 Redhat. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
liali@redhat.com (Li Liang)
"""

from lnst.Controller.Task import ctl
from TestLib import TestLib
from time import sleep
import re
import random

def _run_packet_assert(num, main_if, from_addr, to_addr, proto="icmp", src_port=0, dst_port=0):
    mach = main_if.get_host()

    if proto == "icmp":
        # filter only icmp/icmpv6 ping, and the reuqested addresses
        filter_str = "(icmp && (icmp[icmptype] == icmp-echo || \
                                icmp[icmptype] == icmp-echoreply) \
                       || (icmp6 && (ip6[40] == 128 || \
                                     ip6[40] == 129))) \
                    && src %s && dst %s" % (from_addr, to_addr)
    else:
        filter_str = proto
        if src_port > 0:
            filter_str += " && src port %d" % src_port
        if dst_port > 0:
            filter_str += " && dst port %d" % dst_port

    packet_assert_mod = ctl.get_module("PacketAssert", options = {
                                       "min" : num, "max" : num,
                                       "promiscuous" : True,
                                       "filter" : filter_str,
                                       "interface" : main_if.get_devname()})
    return mach.run(packet_assert_mod, bg=True)

def run_packet_assert(num, main_if, from_if, to_if, ipv, proto="icmp", src_port=0, dst_port=0):
    procs = []

    if ipv in ["ipv4", "both"]:
        ipv4_proc = _run_packet_assert(num, main_if, from_if.get_ip(0),
                                       to_if.get_ip(0), proto, src_port, dst_port)
        procs.append(ipv4_proc)

    if ipv in ["ipv6", "both"]:
        ipv6_proc = _run_packet_assert(num, main_if, from_if.get_ip(1),
                                       to_if.get_ip(1), proto, src_port, dst_port)
        procs.append(ipv6_proc)

    return procs

def test_ip(major, minor):
    return ["192.168.10%d.%d/24" % (major, minor),
            "2002:%d::%d/64" % (major, minor)]
def test_ip_nomask(major, minor):
    return ["192.168.10%d.%d" % (major, minor),
            "2002:%d::%d" % (major, minor)]

def do_task(ctl, hosts, ifaces, aliases):
    tl = TestLib(ctl, aliases)
    m1, m2, sw = hosts
    m1_if1, m2_if1, sw_if1, sw_if2, = ifaces
    m1.sync_resources(modules=["PacketAssert"])

    # configure interfaces
    m1_if1.reset(ip=test_ip(1,1))
    m1_if1_10 = m1.create_vlan(m1_if1, 10, ip=test_ip(2, 1))
    m1_if1_20 = m1.create_vlan(m1_if1, 20, ip=test_ip(3, 1))

    m2_if1.reset(ip=test_ip(1,2))
    m2_if1_10 = m2.create_vlan(m2_if1, 10, ip=test_ip(2, 2))
    m2_if1_20 = m2.create_vlan(m2_if1, 20, ip=test_ip(3, 2))

    br_options = {"vlan_filtering": 1}
    sw_br = sw.create_bridge(slaves=[sw_if1, sw_if2], options=br_options)

    sw_if1.add_br_vlan(10)
    sw_if2.add_br_vlan(10)
    sw_if1.add_br_vlan(20)
    sw_if2.add_br_vlan(20)

    sleep(30)
    
    tl.ping_simple(m1_if1, m2_if1, count=10)
    tl.ping_simple(m1_if1_10, m2_if1_10, count=10)
    tl.ping_simple(m1_if1_20, m2_if1_20, count=10)

    # add qdisc
    sw.run("tc qdisc replace dev %s handle 0: root prio" % sw_if1.get_devname())
    sw.run("tc qdisc add dev %s handle ffff: ingress" % sw_if1.get_devname())

    # dst_ip
    tl.ping_simple(m1_if1, m2_if1, count=10)
    sw.run("tc filter add dev %s parent 0: protocol ip pref 10 flower skip_sw dst_ip %s action drop" % (sw_if2.get_devname(),test_ip_nomask(1,2)[0]))
    sw.run("tc filter add dev %s parent 0: protocol ipv6 pref 11 flower skip_sw dst_ip %s action drop" % (sw_if2.get_devname(),test_ip_nomask(1,2)[1]))
    assert_procs = run_packet_assert(0, m2_if1, m1_if1, m2_if1,
                                     aliases["ipv"])
    tl.ping_simple(m1_if1, m2_if1, fail_expected=True, count=10)
    for assert_proc in assert_procs:
        assert_proc.intr()
    sw.run("tc filter del dev %s parent 0: protocol ip pref 10 flower skip_sw dst_ip %s action drop" % (sw_if2.get_devname(),test_ip_nomask(1,2)[0]))
    sw.run("tc filter del dev %s parent 0: protocol ipv6 pref 11 flower skip_sw dst_ip %s action drop" % (sw_if2.get_devname(),test_ip_nomask(1,2)[1]))

    # src_ip
    tl.ping_simple(m1_if1, m2_if1, count=10)
    sw.run("tc filter add dev %s parent 0: protocol ip pref 10 flower skip_sw src_ip %s action drop" % (sw_if2.get_devname(),test_ip_nomask(1,1)[0]))
    sw.run("tc filter add dev %s parent 0: protocol ipv6 pref 11 flower skip_sw src_ip %s action drop" % (sw_if2.get_devname(),test_ip_nomask(1,1)[1]))
    assert_procs = run_packet_assert(0, m2_if1, m1_if1, m2_if1,
                                     aliases["ipv"])
    tl.ping_simple(m1_if1, m2_if1, fail_expected=True, count=10)
    for assert_proc in assert_procs:
        assert_proc.intr()
    sw.run("tc filter del dev %s parent 0: protocol ip pref 10 flower skip_sw src_ip %s action drop" % (sw_if2.get_devname(),test_ip_nomask(1,1)[0]))
    sw.run("tc filter del dev %s parent 0: protocol ipv6 pref 11 flower skip_sw src_ip %s action drop" % (sw_if2.get_devname(),test_ip_nomask(1,1)[1]))

    # dst_mac
    tl.ping_simple(m1_if1, m2_if1, count=10)
    sw.run("tc filter add dev %s parent 0: protocol ip pref 10 flower skip_sw dst_mac %s action drop" % (sw_if2.get_devname(),m2_if1.get_hwaddr()))
    sw.run("tc filter add dev %s parent 0: protocol ipv6 pref 11 flower skip_sw dst_mac %s action drop" % (sw_if2.get_devname(),m2_if1.get_hwaddr()))
    assert_procs = run_packet_assert(0, m2_if1, m1_if1, m2_if1,
                                     aliases["ipv"])
    tl.ping_simple(m1_if1, m2_if1, fail_expected=True, count=10)
    for assert_proc in assert_procs:
        assert_proc.intr()
    sw.run("tc filter del dev %s parent 0: protocol ip pref 10 flower skip_sw dst_mac %s action drop" % (sw_if2.get_devname(),m2_if1.get_hwaddr()))
    sw.run("tc filter del dev %s parent 0: protocol ipv6 pref 11 flower skip_sw dst_mac %s action drop" % (sw_if2.get_devname(),m2_if1.get_hwaddr()))
   
    # src_mac
    tl.ping_simple(m1_if1, m2_if1, count=10)
    sw.run("tc filter add dev %s parent 0: protocol ip pref 10 flower skip_sw src_mac %s action drop" % (sw_if2.get_devname(),m1_if1.get_hwaddr()))
    sw.run("tc filter add dev %s parent 0: protocol ipv6 pref 11 flower skip_sw src_mac %s action drop" % (sw_if2.get_devname(),m1_if1.get_hwaddr()))
    assert_procs = run_packet_assert(0, m2_if1, m1_if1, m2_if1,
                                     aliases["ipv"])
    tl.ping_simple(m1_if1, m2_if1, fail_expected=True, count=10)
    for assert_proc in assert_procs:
        assert_proc.intr()
    sw.run("tc filter del dev %s parent 0: protocol ip pref 10 flower skip_sw src_mac %s action drop" % (sw_if2.get_devname(),m1_if1.get_hwaddr()))
    sw.run("tc filter del dev %s parent 0: protocol ipv6 pref 11 flower skip_sw src_mac %s action drop" % (sw_if2.get_devname(),m1_if1.get_hwaddr()))
   
    # tcp dst_port
    m1.run("nping --tcp -p 80 -g 50000 %s" % test_ip_nomask(1,2)[0])
    sw.run("tc filter add dev %s parent 0: protocol ip pref 10 flower skip_sw ip_proto tcp dst_port 80 action drop" % sw_if2.get_devname())
    assert_procs = run_packet_assert(0, m2_if1, m1_if1, m2_if1,
                                     aliases["ipv"], "tcp", 50000, 80)
    m1.run("nping --tcp -p 80 -g 50000 %s" % test_ip_nomask(1,2)[0])
    for assert_proc in assert_procs:
        assert_proc.intr()
    sw.run("tc filter del dev %s parent 0: protocol ip pref 10 flower skip_sw ip_proto tcp dst_port 80 action drop" % sw_if2.get_devname())
   
    # tcp src_port
    m1.run("nping --tcp -p 80 -g 50000 %s" % test_ip_nomask(1,2)[0])
    sw.run("tc filter add dev %s parent 0: protocol ip pref 10 flower skip_sw ip_proto tcp src_port 50000 action drop" % sw_if2.get_devname())
    assert_procs = run_packet_assert(0, m2_if1, m1_if1, m2_if1,
                                     aliases["ipv"], "tcp", 50000, 80)
    m1.run("nping --tcp -p 80 -g 50000 %s" % test_ip_nomask(1,2)[0])
    for assert_proc in assert_procs:
        assert_proc.intr()
    sw.run("tc filter del dev %s parent 0: protocol ip pref 10 flower skip_sw ip_proto tcp src_port 50000 action drop" % sw_if2.get_devname())

    # udp dst_port
    m1.run("nping --udp -p 80 -g 50000 %s" % test_ip_nomask(1,2)[0])
    sw.run("tc filter add dev %s parent 0: protocol ip pref 10 flower skip_sw ip_proto udp dst_port 80 action drop" % sw_if2.get_devname())
    assert_procs = run_packet_assert(0, m2_if1, m1_if1, m2_if1,
                                     aliases["ipv"], "udp", 50000, 80)
    m1.run("nping --udp -p 80 -g 50000 %s" % test_ip_nomask(1,2)[0])
    for assert_proc in assert_procs:
        assert_proc.intr()
    sw.run("tc filter del dev %s parent 0: protocol ip pref 10 flower skip_sw ip_proto udp dst_port 80 action drop" % sw_if2.get_devname())
   
    # udp src_port
    m1.run("nping --udp -p 80 -g 50000 %s" % test_ip_nomask(1,2)[0])
    sw.run("tc filter add dev %s parent 0: protocol ip pref 10 flower skip_sw ip_proto udp src_port 50000 action drop" % sw_if2.get_devname())
    assert_procs = run_packet_assert(0, m2_if1, m1_if1, m2_if1,
                                     aliases["ipv"], "udp", 50000, 80)
    m1.run("nping --udp -p 80 -g 50000 %s" % test_ip_nomask(1,2)[0])
    for assert_proc in assert_procs:
        assert_proc.intr()
    sw.run("tc filter del dev %s parent 0: protocol ip pref 10 flower skip_sw ip_proto udp src_port 50000 action drop" % sw_if2.get_devname())

    # vlan_id
    tl.ping_simple(m1_if1_10, m2_if1_10, count=10)
    tl.ping_simple(m1_if1_20, m2_if1_20, count=10)
    sw.run("tc filter add dev %s parent 0: protocol 802.1q flower vlan_id 20 skip_sw action drop" % sw_if2.get_devname())
    assert_procs = run_packet_assert(10, m2_if1_10, m1_if1_10, m2_if1_10,
                                     aliases["ipv"])
    tl.ping_simple(m1_if1_10, m2_if1_10, count=10)
    for assert_proc in assert_procs:
        assert_proc.intr()
    assert_procs = run_packet_assert(0, m2_if1_20, m1_if1_20, m2_if1_20,
                                     aliases["ipv"])
    tl.ping_simple(m1_if1_20, m2_if1_20, count=10, fail_expected=True)
    for assert_proc in assert_procs:
        assert_proc.intr()
    sw.run("tc filter del dev %s parent 0: protocol 802.1q flower vlan_id 20 skip_sw action drop" % sw_if2.get_devname())

    # vlan_prio
    sw.run("tc filter add dev %s parent 0: protocol 802.1q flower vlan_prio 3 skip_sw action drop" % sw_if2.get_devname())
    assert_procs = run_packet_assert(0, m2_if1_10, m1_if1_10, m2_if1_10,
                                     aliases["ipv"], "udp", 0, 9)
    tl.pktgen(m1_if1_10, m2_if1_10, m1_if1_10.get_mtu(), vlan_id=10, vlan_p=3, count=100)
    for assert_proc in assert_procs:
        assert_proc.intr()
    sw.run("tc filter del dev %s parent 0: protocol 802.1q flower vlan_prio 3 skip_sw  action drop" % sw_if2.get_devname())

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
