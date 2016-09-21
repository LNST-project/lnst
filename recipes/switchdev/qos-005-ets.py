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
from random import randint
from time import sleep
import logging

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m2_if1, sw_if1, sw_if2 = ifaces

    m1_if1.reset(ip=["192.168.101.10/24", "2002::1/64"])
    m2_if1.reset(ip=["192.168.101.11/24", "2002::2/64"])

    # For ETS to take effect we need to create congestion in the
    # egress port, so change ports' speeds accordingly.
    sw_if1.set_speed(int(aliases["speed_hi"]))
    sw_if2.set_speed(int(aliases["speed_lo"]))

    sleep(30)

    sw.create_bridge(slaves=[sw_if1, sw_if2], options={"vlan_filtering": 1})
    sw_if1.add_br_vlan(10)
    sw_if2.add_br_vlan(10)

    tl = TestLib(ctl, aliases)

    # Hosts should be set to default values.
    m1.enable_service("lldpad")
    m1_if1.enable_lldp()
    tl.lldp_ets_default_set(m1_if1)
    tl.lldp_pfc_set(m1_if1, prio=[])

    m2.enable_service("lldpad")
    m2_if1.enable_lldp()
    tl.lldp_ets_default_set(m2_if1)
    tl.lldp_pfc_set(m2_if1, prio=[])

    # Get two different random priorities that will represent both
    # competing flows.
    p1 = randint(1, 7)
    p2 = 7 - p1

    # And two random weights for the ETS algorithm.
    bw1 = randint(0, 100)
    bw2 = 100 - bw1

    sw.enable_service("lldpad")
    # Configure the egress port using chosen values.
    sw_if2.enable_lldp()
    tl.lldp_ets_default_set(sw_if2, willing=False)
    tl.lldp_ets_up2tc_set(sw_if2, [(p1, p1), (p2, p2)])
    tl.lldp_ets_tsa_set(sw_if2, [(p1, "ets"), (p2, "ets")],
                        [(p1, bw1), (p2, bw2)])
    tl.lldp_pfc_set(sw_if1, prio=[], willing=False)

    # Make sure the flows are also separated at ingress.
    sw_if1.enable_lldp()
    tl.lldp_ets_default_set(sw_if1, willing=False)
    tl.lldp_ets_up2tc_set(sw_if1, [(p1, p1), (p2, p2)])
    tl.lldp_pfc_set(sw_if1, prio=[], willing=False)

    # ETS won't work if there aren't enough packets in the shared buffer
    # awaiting transmission. Therefore, let each port take up to ~98% of
    # free buffer in the pool and each PG/TC up to 50%. We assume pools
    # 0 and 4 are configured with non-zero sizes.
    tl.devlink_pool_thtype_set(sw, sw_if1.get_devlink_name(), 0, False)
    tl.devlink_port_tc_quota_set(sw_if1, p1, True, 0, 10)
    tl.devlink_port_tc_quota_set(sw_if1, p2, True, 0, 10)
    tl.devlink_port_quota_set(sw_if1, 0, 16)
    tl.devlink_pool_thtype_set(sw, sw_if1.get_devlink_name(), 4, False)
    tl.devlink_port_tc_quota_set(sw_if2, p1, False, 4, 10)
    tl.devlink_port_tc_quota_set(sw_if2, p2, False, 4, 10)
    tl.devlink_port_quota_set(sw_if2, 4, 16)

    tl.ping_simple(m1_if1, m2_if1)

    # Record the stats before the test for comparison.
    tx_stats_p1_t0 = tl.get_tx_prio_stats(sw_if2, p1)
    tx_stats_p2_t0 = tl.get_tx_prio_stats(sw_if2, p2)

    # Transmit each flow using as many threads as possible, thereby
    # making sure the egress port is congested. Otherwise, ETS won't
    # take effect.
    num_cpus = m1.get_num_cpus()
    packet_count = 10 * 10 ** 6
    thread_option = ["vlan_p {}".format(p1)] * (num_cpus / 2)
    thread_option += ["vlan_p {}".format(p2)] * (num_cpus / 2)
    tl.pktgen(m1_if1, m2_if1, m1_if1.get_mtu(), thread_option=thread_option,
              vlan_id=10, count=packet_count, flag="QUEUE_MAP_CPU")

    # Record the stats after the test and check if ETS worked as
    # expected.
    tx_stats_p1_t1 = tl.get_tx_prio_stats(sw_if2, p1)
    tx_stats_p2_t1 = tl.get_tx_prio_stats(sw_if2, p2)
    p1_count = tx_stats_p1_t1 - tx_stats_p1_t0
    p2_count = tx_stats_p2_t1 - tx_stats_p2_t0

    total = p1_count + p2_count
    bw1_oper = p1_count / float(total) * 100
    bw2_oper = p2_count / float(total) * 100

    # Log useful information.
    logging.info("p1_count={} p2_count={}".format(p1_count, p2_count))
    bw_str = "bw1_oper={:.2f}% ({}%) bw2_oper={:.2f}% ({}%)".format(bw1_oper,
                                                                    bw1,
                                                                    bw2_oper,
                                                                    bw2)
    logging.info(bw_str)
    # The 802.1Qaz standard states a deviation of no more than 10%.
    if abs(bw1_oper - bw1) < 10 and abs(bw2_oper - bw2) < 10:
        err_msg = ""
    else:
        err_msg = "bandwidth deviation exceeded 10%"
    tl.custom(sw, "ets test", err_msg)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
