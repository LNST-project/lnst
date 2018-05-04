"""
Copyright 2017 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
petrm@mellanox.com (Petr Machata)
"""

from lnst.Controller.Task import ctl
from TestLib import TestLib, vrf, dummy, gre
from ipip_common import ping_test, encap_route, \
                        add_forward_route, connect_host_ifaces, \
                        test_ip, ipv4, ipv6, refresh_addrs
from time import sleep
import logging

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    (m1_if1_10, m1_if1_20,
     m2_if1_10, m2_if1_20,
     sw_if1_10, sw_if1_20,
     sw_if2_10, sw_if2_20) = ifaces

    m1_if1_10.add_nhs_route(ipv4(test_ip(2, 0)), [ipv4(test_ip(1, 1, []))])
    m1_if1_10.add_nhs_route(ipv6(test_ip(2, 0)), [ipv6(test_ip(1, 1, []))])
    m1_if1_20.add_nhs_route(ipv4(test_ip(4, 0)), [ipv4(test_ip(3, 1, []))])
    m1_if1_20.add_nhs_route(ipv6(test_ip(4, 0)), [ipv6(test_ip(3, 1, []))])

    vrf_None = None
    tl = TestLib(ctl, aliases)

    # - Test migration of several tunnels tied to a single dummy. Have a
    #   setup like below, and test end-to-end ping from 1.33 to 2.33, and
    #   lack of end-to-end ping from 3.33 to 4.33. Then migrate d to svu2
    #   and test that 2.33 doesn't ping anymore, but 4.33 now does.
    #
    #   +-- M1 ------------+    +-- SW -----------------------------+
    #   |                  |    | +-- svo ------------------------+ |
    #   |                  |    | |          sg1 1.2.3.4/31       | |
    #   |        1.33/24 +-|----|-|-+ 1.1/24  +                   | |
    #   |                  |    | |           |  sg2 1.2.3.6/31   | |
    #   |        3.33/24 +-|----|-|-+ 3.1/24  |   +               | |
    #   +------------------+    | +-------------------------------+ |
    #                           |             |   |                 |
    #   +-- M2 ------------+    | +-- svu1 -----------------------+ |
    #   |                  |    | |           \   /               | |
    #   |    2.33/32 md1 + |    | |            \ /   1.2.3.4/32   | |
    #   | 1.2.3.5/31 mg1 + |    | |             + sd 1.2.3.6/32   | |
    #   |        99.2/24 +-|----|-|-+ 99.1/24                     | |
    #   |                  |    | |                               | |
    #   |                  |    | +-------------------------------+ |
    #   |                  |    |                                   |
    #   |    4.33/32 md2 + |    | +-- svu2 -----------------------+ |
    #   | 1.2.3.7/31 mg2 + |    | |                               | |
    #   |        88.2/24 +-|----|-|-+ 88.1/24                     | |
    #   |                  |    | +-------------------------------+ |
    #   +------------------+    +-----------------------------------+

    logging.info("--- Migrate bound device shared by several tunnels")
    with vrf(sw) as svo, \
         vrf(sw) as svu1, \
         vrf(sw) as svu2, \
         \
         encap_route(m2, vrf_None, 1, "mg1", ip=ipv4), \
         encap_route(m2, vrf_None, 1, "mg1", ip=ipv6), \
         \
         encap_route(m2, vrf_None, 3, "mg2", ip=ipv4), \
         encap_route(m2, vrf_None, 3, "mg2", ip=ipv6), \
         \
         dummy(sw, svu1, ip=["1.2.3.4/32", "1.2.3.6/32"]) as sd, \
         gre(sw, sd, svo,
             tos="inherit",
             local_ip="1.2.3.4",
             remote_ip="1.2.3.5") as sg1, \
         gre(sw, sd, svo,
             tos="inherit",
             local_ip="1.2.3.6",
             remote_ip="1.2.3.7") as sg2, \
         encap_route(sw, svo, 2, sg1, ip=ipv4), \
         encap_route(sw, svo, 2, sg1, ip=ipv6), \
         encap_route(sw, svo, 4, sg2, ip=ipv4), \
         encap_route(sw, svo, 4, sg2, ip=ipv6):

        connect_host_ifaces(sw, sw_if1_10, svo, sw_if2_10, svu1)
        refresh_addrs(sw, sw_if1_10)
        refresh_addrs(sw, sw_if2_10)

        connect_host_ifaces(sw, sw_if1_20, svo, sw_if2_20, svu2)
        refresh_addrs(sw, sw_if1_20)
        refresh_addrs(sw, sw_if2_20)

        add_forward_route(sw, svu1, "1.2.3.5", ipv4(test_ip(99, 2, [])))
        add_forward_route(sw, svu2, "1.2.3.7", ipv4(test_ip(88, 2, [])))
        add_forward_route(m2, vrf_None, "1.2.3.4", ipv4(test_ip(99, 1, [])))
        add_forward_route(m2, vrf_None, "1.2.3.6", ipv4(test_ip(88, 1, [])))

        def quick_test(tun1_ipv4_fail, tun1_ipv6_fail,
                       tun2_ipv4_fail, tun2_ipv6_fail):
            sleep(5)
            ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1_10, sg1,
                      count=25, fail_expected=tun1_ipv6_fail, ipv6=True)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1_10, sg1,
                      count=25, fail_expected=tun1_ipv4_fail)

            ping_test(tl, m1, sw, ipv6(test_ip(4, 33, [])), m1_if1_20, None,
                      count=25, fail_expected=tun2_ipv6_fail, ipv6=True)
            ping_test(tl, m1, sw, ipv4(test_ip(4, 33, [])), m1_if1_20, None,
                      count=25, fail_expected=tun2_ipv4_fail)

        sleep(15)
        quick_test(False, False, True, True)

        sw.run("ip l s dev %s master %s" % (sd.get_devname(), svu2))
        sleep(5)
        quick_test(True, True, False, False)

        sw.run("ip l s dev %s master %s" % (sd.get_devname(), svu1))
        sleep(5)
        quick_test(False, False, True, True)

        sw.run("ip l s dev %s master %s" % (sd.get_devname(), svu2))
        sleep(5)
        quick_test(True, True, False, False)

        sw.run("ip l s dev %s nomaster" % sd.get_devname())
        sleep(5)
        quick_test(True, True, True, True)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1.10"),
         ctl.get_host("machine1").get_interface("if1.20"),
         ctl.get_host("machine2").get_interface("if1.10"),
         ctl.get_host("machine2").get_interface("if1.20"),
         ctl.get_host("switch").get_interface("if1.10"),
         ctl.get_host("switch").get_interface("if1.20"),
         ctl.get_host("switch").get_interface("if2.10"),
         ctl.get_host("switch").get_interface("if2.20")],
        ctl.get_aliases())
