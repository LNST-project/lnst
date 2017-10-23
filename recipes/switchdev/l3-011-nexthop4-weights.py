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

def ping(ctl, if1, if2):
        m1 = if1.get_host()
        m1.sync_resources(modules=["IcmpPing"])

        ping_mod = ctl.get_module("IcmpPing",
                                  options={
                                  "addr": if2.get_ip(1),
                                  "count": 100,
                                  "interval": 0.2,
                                  "iface" : if1.get_devname(),
                                  "limit_rate": 90})
        m1.run(ping_mod)

def pktgen(ctl, if1, if2, neigh_mac):
        m1 = if1.get_host()
        m1.sync_resources(modules=["PktgenTx"])

        pktgen_option = ["pkt_size {}".format(if1.get_mtu()),
                         "clone_skb 0",
                         "count {}".format(10 * 10 ** 6),
                         "dst_mac {}".format(neigh_mac),
                         "dst {}".format(if2.get_ip(1)),
                         "udp_src_min 1024", "udp_src_max 4096",
                         "udp_dst_min 1024", "udp_dst_max 4096",
                         "flag UDPSRC_RND", "flag UDPDST_RND"]
        pktgen_mod = ctl.get_module("PktgenTx",
                                    options={
                                    "netdev_name": if1.get_devname(),
                                    "pktgen_option": pktgen_option})
        m1.run(pktgen_mod, timeout=600)

def check_res(tl, m, if2_weight, if3_weight, if2_pkts, if3_pkts):
    weight_ratio = float(if2_weight) / float(if3_weight)
    msg = "Weights ratio: if2 ({}) / if3 ({}) = {:f}"
    logging.info(msg.format(if2_weight, if3_weight, weight_ratio))

    pkts_ratio = float(if2_pkts) / float(if3_pkts)
    msg = "Tx-ed packets ratio: if2 ({}) / if3 ({}) = {:f}"
    logging.info(msg.format(if2_pkts, if3_pkts, pkts_ratio))

    if (abs(weight_ratio - pkts_ratio) / weight_ratio) <= 0.1:
        err_msg=""
    else:
        err_msg = "Too large discrepancy (> 10%) in ratio"
    tl.custom(m, "Ratio comparison", err_msg)

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m2_if1, m2_if2, sw_if1, sw_if2, sw_if3 = ifaces

    subnet0 = aliases["subnet0"] + ".0/24"
    subnet1 = aliases["subnet1"] + ".0/24"
    subnet2 = aliases["subnet2"] + ".0/24"
    subnet3 = aliases["subnet3"] + ".0/24"
    weight0 = int(aliases["weight0"])
    weight1 = int(aliases["weight1"])

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

    cmd = "ip -4 route add {subnet} nexthop via {gw_ip} dev {nh_dev}"
    m1.run(cmd.format(subnet=subnet3, gw_ip=sw_if1.get_ip(0),
                      nh_dev=m1_if1.get_devname()))

    cmd = ("ip -4 route add {subnet} nexthop via {gw_ip0} dev {nh_dev0} "
           "nexthop via {gw_ip1} dev {nh_dev1}")
    m2.run(cmd.format(subnet=subnet0, gw_ip0=sw_if2.get_ip(0),
                      nh_dev0=m2_if1.get_devname(), gw_ip1=sw_if3.get_ip(0),
                      nh_dev1=m2_if2.get_devname()))

    cmd = ("ip -4 route add {subnet} nexthop via {gw_ip0} dev {nh_dev0} "
           "weight {w0} nexthop via {gw_ip1} dev {nh_dev1} weight {w1}")
    sw.run(cmd.format(subnet=subnet3, gw_ip0=m2_if1.get_ip(0),
                      nh_dev0=sw_if2.get_devname(), w0=weight0,
                      gw_ip1=m2_if2.get_ip(0), nh_dev1=sw_if3.get_devname(),
                      w1=weight1))

    # Make sure the kernel uses L4 fields for multipath hash, since we
    # are going to use random UDP source and destination ports.
    sw.run("sysctl -w net.ipv4.fib_multipath_hash_policy=1")

    sleep(30)

    # Basic sanity check to make sure test is not failing due to
    # setup issues.
    ping(ctl, m1_if1, m2_if2)

    if2_pre = sw_if2.link_stats()["tx_packets"]
    if3_pre = sw_if3.link_stats()["tx_packets"]

    # Send different flows from m1 to m2, so that traffic is hashed
    # according to provided weights.
    pktgen(ctl, m1_if1, m2_if2, sw_if1.get_hwaddr())

    if2_post = sw_if2.link_stats()["tx_packets"]
    if3_post = sw_if3.link_stats()["tx_packets"]

    check_res(tl, m1, weight0, weight1, if2_post - if2_pre, if3_post - if3_pre)

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
