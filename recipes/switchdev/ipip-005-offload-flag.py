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
                        test_ip, ipv4, ipv6
from time import sleep
import logging

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m2_if1, sw_if1, sw_if2 = ifaces

    vrf_None = None
    tl = TestLib(ctl, aliases)
    sw_if1.reset(ip=test_ip(1, 2))
    sw_if2.reset(ip=test_ip(99,1))

    # Test that offloaded routes do have "offload" flag.
    with dummy(sw, vrf_None, ip=["1.2.3.4/32"]) as d:
        with gre(sw, None, vrf_None,
                 tos="inherit",
                 local_ip="1.2.3.4",
                 remote_ip="1.2.3.5") as g, \
             encap_route(sw, vrf_None, 2, g, ip=ipv4), \
             encap_route(sw, vrf_None, 2, g, ip=ipv6):
            sleep(15)

            ulip = test_ip(2, 0, [24, 64])
            (r4,), _ = sw.get_routes("table 0 %s" % ipv4(ulip))
            if "offload" not in r4["flags"]:
                tl.custom(sw, "ipip", "IPv4 encap route not offloaded")

            (r6,), _ = sw.get_routes("table 0 %s" % ipv6(ulip))
            if "offload" not in r6["flags"]:
                tl.custom(sw, "ipip", "IPv6 encap route not offloaded")

            (dcr4,), _ = sw.get_routes("table local 1.2.3.4")
            if "offload" not in dcr4["flags"]:
                tl.custom(sw, "ipip", "IPv4 decap route not offloaded")

        sleep(5)
        (dcr4,), _ = sw.get_routes("table local 1.2.3.4")
        if "offload" in dcr4["flags"]:
            tl.custom(sw, "ipip", "IPv4 decap still flagged offloaded")

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
