"""
Copyright 2017 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
idosch@mellanox.com (Ido Schimmel)
"""

from lnst.Controller.Task import ctl
from TestLib import TestLib
from time import sleep
import logging

def ping(ctl, if1, dst):
        m1 = if1.get_host()
        m1.sync_resources(modules=["Icmp6Ping"])

        ping_mod = ctl.get_module("Icmp6Ping",
                                  options={
                                  "addr": dst,
                                  "count": 100,
                                  "interval": 0.2,
                                  "iface" : if1.get_devname(),
                                  "limit_rate": 90})
        m1.run(ping_mod)

def pktgen_l4(ctl, if1, dst, neigh_mac):
        m1 = if1.get_host()
        m1.sync_resources(modules=["PktgenTx"])

        pktgen_option = ["pkt_size {}".format(if1.get_mtu()),
                         "clone_skb 0",
                         "count {}".format(10 * 10 ** 6),
                         "dst_mac {}".format(neigh_mac),
                         "src6 {}".format(if1.get_ip(0)),
                         "dst6 {}".format(dst),
                         "udp_src_min 1024", "udp_src_max 4096",
                         "udp_dst_min 1024", "udp_dst_max 4096",
                         "flag UDPSRC_RND", "flag UDPDST_RND", "flag IPV6"]
        pktgen_mod = ctl.get_module("PktgenTx",
                                    options={
                                    "netdev_name": if1.get_devname(),
                                    "pktgen_option": pktgen_option})
        m1.run(pktgen_mod, timeout=600)

def pktgen_l3(ctl, if1, neigh_mac, dst_subnet):
        m1 = if1.get_host()
        m1.sync_resources(modules=["PktgenTx"])

        pktgen_option = ["pkt_size {}".format(if1.get_mtu()),
                         "clone_skb 0",
                         "count {}".format(10 * 10 ** 6),
                         "dst_mac {}".format(neigh_mac),
                         "dst6_min {}".format(dst_subnet + "::1"),
                         "dst6_max {}".format(dst_subnet + "::cafe"),
                         "src6 {}".format(if1.get_ip(0)),
                         "udp_src_min 1024", "udp_src_max 1024",
                         "udp_dst_min 1024", "udp_dst_max 1024",
                         "flag IPDST_RND", "flag IPV6"]
        pktgen_mod = ctl.get_module("PktgenTx",
                                    options={
                                    "netdev_name": if1.get_devname(),
                                    "pktgen_option": pktgen_option})
        m1.run(pktgen_mod, timeout=600)

def check_res(tl, m, if2_pkts, if3_pkts, multipath):
    msg = "Tx-ed packets: if2 ({}) , if3 ({})"
    logging.info(msg.format(if2_pkts, if3_pkts))

    # In case multipathing took place, following ratio should be very
    # close to 0. Otherwise, very close to 1.
    ratio = abs(if2_pkts - if3_pkts) / float(if2_pkts + if3_pkts)
    if multipath:
        err_msg = "" if ratio < 0.1 else "Multipathing didn't occur when should"
    else:
        err_msg = "" if ratio > 0.9 else "Multipathing occurred when shouldn't"
    tl.custom(m, "Multipath test", err_msg)

def multipath_test(ctl, hosts, ifaces, aliases, l3, should_multipath):
    m1_if1, m2_if1, m2_if2, sw_if1, sw_if2, sw_if3 = ifaces
    tl = TestLib(ctl, aliases)
    m1, m2, sw = hosts

    if2_pre = sw_if2.link_stats()["tx_packets"]
    if3_pre = sw_if3.link_stats()["tx_packets"]

    if l3:
        pktgen_l3(ctl, m1_if1, sw_if1.get_hwaddr(), aliases["subnet3"])
    else:
        pktgen_l4(ctl, m1_if1, m2_if2.get_ip(1), sw_if1.get_hwaddr())

    if2_post = sw_if2.link_stats()["tx_packets"]
    if3_post = sw_if3.link_stats()["tx_packets"]

    check_res(tl, m1, if2_post - if2_pre, if3_post - if3_pre, should_multipath)

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m2_if1, m2_if2, sw_if1, sw_if2, sw_if3 = ifaces

    subnet0 = aliases["subnet0"] + "::/32"
    subnet1 = aliases["subnet1"] + "::/32"
    subnet2 = aliases["subnet2"] + "::/32"
    subnet3 = aliases["subnet3"] + "::/32"

    tl = TestLib(ctl, aliases)

    # +----------------------------------+
    # |                                  |
    # |                                  |
    # | sw_if1            sw_if2  sw_if3 |
    # +---+-----------------+-------+----+
    #     |                 |       |
    #     |                 |       |
    #     |                 |       |
    #     |                 |       |
    #     +                 +       +
    #   m1_if1            m2_if1  m2_if2

    cmd = "ip -6 route add {subnet} nexthop via {gw_ip} dev {nh_dev}"
    m1.run(cmd.format(subnet=subnet3, gw_ip=sw_if1.get_ip(0),
                      nh_dev=m1_if1.get_devname()))

    cmd = ("ip -6 route add {subnet} nexthop via {gw_ip0} dev {nh_dev0} "
           "nexthop via {gw_ip1} dev {nh_dev1}")
    m2.run(cmd.format(subnet=subnet0, gw_ip0=sw_if2.get_ip(0),
                      nh_dev0=m2_if1.get_devname(), gw_ip1=sw_if3.get_ip(0),
                      nh_dev1=m2_if2.get_devname()))

    cmd = ("ip -6 route add {subnet} nexthop via {gw_ip0} dev {nh_dev0} "
           "nexthop via {gw_ip1} dev {nh_dev1}")
    sw.run(cmd.format(subnet=subnet3, gw_ip0=m2_if1.get_ip(0),
                      nh_dev0=sw_if2.get_devname(), gw_ip1=m2_if2.get_ip(0),
                      nh_dev1=sw_if3.get_devname()))

    sleep(30)

    # Basic sanity check to make sure test is not failing due to
    # setup issues.
    ping(ctl, m1_if1, m2_if2.get_ip(1))

    multipath_test(ctl, hosts, ifaces, aliases, False, False)

    multipath_test(ctl, hosts, ifaces, aliases, True, True)

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
