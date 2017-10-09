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
                        test_ip, ipv4
from time import sleep
import logging

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m2_if1, sw_if1, sw_if2 = ifaces

    m1_if1.add_nhs_route(ipv4(test_ip(2, 0)), [ipv4(test_ip(1, 1, []))])
    m2_if1.add_nhs_route("1.2.3.4/32", [ipv4(test_ip(99, 1, []))])

    vrf_None = None
    tl = TestLib(ctl, aliases)
    sw_if1.reset(ip=test_ip(1, 2))
    sw_if2.reset(ip=test_ip(99,1))

    # Test that non-IPIP traffic gets to slow path.
    with dummy(sw, vrf_None, ip=["1.2.3.4/32"]) as d, \
         gre(sw, None, vrf_None,
             tos="inherit",
             local_ip="1.2.3.4",
             remote_ip="1.2.3.5") as g, \
         encap_route(sw, vrf_None, 2, g, ip=ipv4):
        sleep(15)
        ping_test(tl, m2, sw, "1.2.3.4", m2_if1, g, count=20)

    # Configure the wrong interface on M2 to test that the traffic gets trapped
    # to CPU.
    with encap_route(m2, vrf_None, 1, "gre3"):

        add_forward_route(sw, vrf_None, "1.2.3.5")

        with dummy(sw, vrf_None, ip=["1.2.3.4/32"]) as d, \
             gre(sw, None, vrf_None,
                 local_ip="1.2.3.4",
                 remote_ip="1.2.3.5") as g:
            sleep(15)

            before_stats = sw_if2.link_stats()["rx_packets"]
            ping_test(tl, m2, sw, ipv4(test_ip(1, 33, [])), m2_if1, g,
                      count=20, fail_expected=True)
            after_stats = sw_if2.link_stats()["rx_packets"]
            delta = after_stats - before_stats
            if delta < 15:
                tl.custom(sw, "ipip",
                        "Too few packets (%d) observed in slow path" % delta)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
