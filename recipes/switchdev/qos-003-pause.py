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

def get_stats(tl, rx_if, tx_if, prio):
    return tl.get_rx_prio_stats(rx_if, prio), tl.get_tx_prio_stats(tx_if, prio)

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m2_if1, sw_if1, sw_if2 = ifaces

    m1_if1.reset(ip=["192.168.101.10/24", "2002::1/64"])
    m2_if1.reset(ip=["192.168.101.11/24", "2002::2/64"])

    # Make sure we'll get the buffers congested.
    sw_if1.set_speed(int(aliases["speed_hi"]))
    sw_if2.set_speed(int(aliases["speed_lo"]))

    sleep(30)

    sw.create_bridge(slaves=[sw_if1, sw_if2], options={"vlan_filtering": 1})
    sw_if1.add_br_vlan(10)
    sw_if2.add_br_vlan(10)

    # Packets can only stay in the headroom if the egress quotas
    # of the egress port are set to the maximum.
    tl = TestLib(ctl, aliases)
    tl.devlink_port_etc_quota_max_set(sw_if2, 0)

    # PAUSE frames and PFC can't be enabled simultaneously.
    sw.enable_service("lldpad")
    sw_if1.enable_lldp()
    tl.lldp_pfc_set(sw_if1, [], willing=False)

    m1.enable_service("lldpad")
    m1_if1.enable_lldp()
    tl.lldp_pfc_set(m1_if1, [])

    # All the traffic should be directed to the same TC at egress.
    sw_if2.enable_lldp()
    tl.lldp_ets_default_set(sw_if2, willing=False)

    m2.enable_service("lldpad")
    m2_if1.enable_lldp()
    tl.lldp_ets_default_set(m2_if1)

    tl.ping_simple(m1_if1, m2_if1)

    packet_count = 40 * 10 ** 6
    prio = randint(1, 7)
    # Make sure we get packet loss without PAUSE frames.
    _, tx_stats_t0 = get_stats(tl, sw_if1, sw_if2, prio)
    tl.pktgen(m1_if1, m2_if1, m1_if1.get_mtu(), vlan_id=10, vlan_p=prio,
              count=packet_count)
    _, tx_stats_t1 = get_stats(tl, sw_if1, sw_if2, prio)
    tl.check_stats(sw_if1, tx_stats_t1 - tx_stats_t0, packet_count,
                   "tx prio {}".format(prio), fail=True)

    sw_if1.set_pause_on()
    m1_if1.set_pause_on()

    for prio in range(1, 8):
        rx_stats_t0, tx_stats_t0 = get_stats(tl, sw_if1, sw_if2, prio)
        tl.pktgen(m1_if1, m2_if1, m1_if1.get_mtu(), vlan_id=10, vlan_p=prio,
                  count=packet_count)
        rx_stats_t1, tx_stats_t1 = get_stats(tl, sw_if1, sw_if2, prio)

        tl.check_stats(sw_if1, rx_stats_t1 - rx_stats_t0, packet_count,
                       "rx prio {}".format(prio))
        tl.check_stats(sw_if2, tx_stats_t1 - tx_stats_t0, packet_count,
                       "tx prio {}".format(prio))

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
