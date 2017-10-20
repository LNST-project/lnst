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

    m1_if1.add_nhs_route(ipv4(test_ip(2, 0)), [ipv4(test_ip(1, 1, []))])
    m1_if1.add_nhs_route(ipv6(test_ip(2, 0)), [ipv6(test_ip(1, 1, []))])
    m2_if1.add_nhs_route("1.2.3.4/32", [ipv4(test_ip(99, 1, []))])

    vrf_None = None
    tl = TestLib(ctl, aliases)
    sw_if1.reset(ip=test_ip(1, 1))
    sw_if2.reset(ip=test_ip(99,1))

    logging.info("=== Hierarchical configuration")
    with vrf(sw) as vrf_u, \
         vrf(sw) as vrf_o:
        connect_host_ifaces(sw, sw_if1, vrf_o, sw_if2, vrf_u)
        sw_if1.reset()
        sw_if2.reset()
        add_forward_route(sw, vrf_u, "1.2.3.5")

        with encap_route(m2, vrf_None, 1, "gre1", ip=ipv4), \
             encap_route(m2, vrf_None, 1, "gre1", ip=ipv6):
            # - Set up encap route before decap route.
            # - Tear down encap route before decap route.
            logging.info("--- Eup, Dup, Edown, Ddown")
            with dummy(sw, vrf_u) as d, \
                 gre(sw, d, vrf_o,
                     tos="inherit",
                     local_ip="1.2.3.4",
                     remote_ip="1.2.3.5") as g, \
                 encap_route(sw, vrf_o, 2, g, ip=ipv4), \
                 encap_route(sw, vrf_o, 2, g, ip=ipv6):

                sleep(5)
                d.set_addresses(["1.2.3.4/32"])
                sleep(15)
                ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1, g,
                          ipv6=True)
                ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g)

            # - Set up decap route before encap route.
            # - Tear down decap route before encap route.
            logging.info("--- Dup, Eup, Ddown, Edown")
            with dummy(sw, vrf_u, ip=["1.2.3.4/32"]) as d, \
                 gre(sw, d, vrf_o,
                     tos="inherit",
                     local_ip="1.2.3.4",
                     remote_ip="1.2.3.5") as g:

                with encap_route(sw, vrf_o, 2, g, ip=ipv4), \
                     encap_route(sw, vrf_o, 2, g, ip=ipv6):
                    sleep(15)
                    ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1, g,
                              ipv6=True)
                    ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g)

                d.set_addresses([])
                g.set_addresses([])

            # - Set up two tunnels and test route replacement.
            logging.info("--- Route replacement")
            with dummy(sw, vrf_u, ip=["1.2.3.6/32"]) as d1, \
                 gre(sw, d1, vrf_o,
                     tos="inherit",
                     local_ip="1.2.3.6",
                     remote_ip="1.2.3.7") as g1, \
                 dummy(sw, vrf_u, ip=["1.2.3.4/32"]) as d2, \
                 gre(sw, d2, vrf_o,
                     tos="inherit",
                     local_ip="1.2.3.4",
                     remote_ip="1.2.3.5") as g2:

                def quick_test(ipv4_fail, ipv6_fail):
                    sleep(5)
                    ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1, g1,
                              count=25, fail_expected=ipv6_fail, ipv6=True)
                    ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g1,
                              count=25, fail_expected=ipv4_fail)

                # Replacing IPv4 route should cause the IPv4 traffic to drop and
                # not affect the IPv6 one.
                encap_route(sw, vrf_o, 2, g2, ip=ipv6).do("add")
                encap_route(sw, vrf_o, 2, g1, ip=ipv4).do("add")
                quick_test(True, False)

                encap_route(sw, vrf_o, 2, g2, ip=ipv4).do("replace")
                quick_test(False, False)

                encap_route(sw, vrf_o, 2, g1, ip=ipv4).do("replace")
                quick_test(True, False)

                encap_route(sw, vrf_o, 2, g2, ip=ipv4).do("replace")
                quick_test(False, False)

                # And vice versa.
                encap_route(sw, vrf_o, 2, g1, ip=ipv6).do("replace")
                quick_test(False, True)

                encap_route(sw, vrf_o, 2, g2, ip=ipv6).do("replace")
                quick_test(False, False)

                encap_route(sw, vrf_o, 2, g1, ip=ipv6).do("replace")
                quick_test(False, True)

                encap_route(sw, vrf_o, 2, g2, ip=ipv6).do("replace")
                quick_test(False, False)

                # Done.
                encap_route(sw, vrf_o, 2, g2, ip=ipv4).do("del")
                encap_route(sw, vrf_o, 2, g2, ip=ipv6).do("del")

        with dummy(sw, vrf_u, ip=["1.2.3.4/32"]) as d:

            # - Test with ikey/okey.
            logging.info("--- ikey/okey")
            with encap_route(m2, vrf_None, 1, "gre2"), \
                 gre(sw, d, vrf_o,
                     tos="inherit",
                     local_ip="1.2.3.4",
                     remote_ip="1.2.3.5",
                     ikey=2222, okey=1111) as g, \
                 encap_route(sw, vrf_o, 2, g):

                sleep(15)
                ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g)

            # - Slow path: non-inherit TOS.
            logging.info("--- non-inherit TOS (slow path)")
            with encap_route(m2, vrf_None, 1, "gre1"), \
                 gre(sw, d, vrf_o,
                     tos="0x10",
                     local_ip="1.2.3.4",
                     remote_ip="1.2.3.5") as g, \
                 encap_route(sw, vrf_o, 2, g):

                sleep(15)
                ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g,
                          require_fastpath=False)

            # - Slow path: csum-enabled tunnel.
            logging.info("--- checksum (slow path)")
            with encap_route(m2, vrf_None, 1, "gre3"), \
                 gre(sw, d, vrf_o,
                     tos="inherit",
                     local_ip="1.2.3.4",
                     remote_ip="1.2.3.5",
                     key=3333, csum=True) as g, \
                 encap_route(sw, vrf_o, 2, g):

                sleep(15)
                ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g,
                          require_fastpath=False)

        # - Enable two dummy devices in different VRFs with the decap address.
        #   The driver crashes on tunnel tear-down if it incorrectly assigned
        #   both decaps to the same tunnel.
        logging.info("--- the same tunnel local address in two VRFs")
        with vrf(sw) as vrf3, \
             dummy(sw, vrf_u) as d, \
             gre(sw, d, vrf_o,
                 local_ip="1.2.3.4",
                 remote_ip="1.2.3.5") as g, \
             encap_route(sw, vrf3, 2, g), \
             dummy(sw, vrf3) as d3:

            sleep(5)
            d.set_addresses(["1.2.3.4/32"])
            d3.set_addresses(["1.2.3.4/32"])
            sleep(5)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
