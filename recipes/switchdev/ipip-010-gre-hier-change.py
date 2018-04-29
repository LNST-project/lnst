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

    logging.info("=== Hierarchical configuration, 'ip t change'")
    with vrf(sw) as vrf_u, \
         vrf(sw) as vrf_o, \
         vrf(sw) as vrf3, \
         dummy(sw, vrf_u, ip=["1.2.3.4/32"]) as d:
        connect_host_ifaces(sw, sw_if1, vrf_o, sw_if2, vrf_u)
        sw_if1.reset()
        sw_if2.reset()
        add_forward_route(sw, vrf_u, "1.2.3.5")

        logging.info("--- create tunnel with a down underlay")
        d.set_link_down()
        with encap_route(m2, vrf_None, 1, "gre1", ip=ipv4), \
             encap_route(m2, vrf_None, 1, "gre1", ip=ipv6), \
             gre(sw, d, vrf_o,
                 tos="inherit",
                 local_ip="1.2.3.4",
                 remote_ip="1.2.3.5") as g, \
             encap_route(sw, vrf_o, 2, g, ip=ipv4), \
             encap_route(sw, vrf_o, 2, g, ip=ipv6):

            sleep(15)
            ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1, g,
                      count=100, fail_expected=True, ipv6=True)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g,
                      count=100, fail_expected=True)

        d.set_link_up()

        logging.info("--- change of bound device")
        with encap_route(m2, vrf_None, 1, "gre1", ip=ipv4), \
             encap_route(m2, vrf_None, 1, "gre1", ip=ipv6), \
             dummy(sw, vrf3, ip=["1.2.3.4/32"]) as d2, \
             gre(sw, d2, vrf_o,
                 tos="inherit",
                 local_ip="1.2.3.4",
                 remote_ip="1.2.3.5") as g, \
             encap_route(sw, vrf_o, 2, g, ip=ipv4), \
             encap_route(sw, vrf_o, 2, g, ip=ipv6):

            sleep(15)
            ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1, g,
                      count=25, fail_expected=True, ipv6=True)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g,
                      count=25, fail_expected=True)

            sw.run("ip t change name %s dev %s"
                   % (g.get_devname(), d.get_devname()))

            sleep(5)
            ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1, g,
                      ipv6=True)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g)

            logging.info("--- bound device up/down")
            # Now change back to `d2', set `d' down and change to it again.
            # Traffic shouldn't flow.
            # There's a complementary test in ipip-006 to make sure that
            # decap-only flow still works even if bound device is down.
            sw.run("ip t change name %s dev %s"
                   % (g.get_devname(), d2.get_devname()))
            d.set_link_down()
            sleep(5)

            sw.run("ip t change name %s dev %s"
                   % (g.get_devname(), d.get_devname()))

            sleep(5)
            ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1, g,
                      count=25, fail_expected=True, ipv6=True)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g,
                      count=25, fail_expected=True)

            # Set `d' up while it's the bound device. Traffic should flow again.
            d.set_link_up()
            sleep(5)

            ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1, g,
                      ipv6=True)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g)

            # Set `d' down while it's the bound device.
            d.set_link_down()
            sleep(5)

            ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1, g,
                      count=25, fail_expected=True, ipv6=True)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g,
                      count=25, fail_expected=True)

            # Set `d' back up again to make sure it's stable.
            d.set_link_up()
            sleep(5)

            ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1, g,
                      ipv6=True)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g)

        logging.info("--- remote change")
        with encap_route(m2, vrf_None, 1, "gre1", ip=ipv4), \
             encap_route(m2, vrf_None, 1, "gre1", ip=ipv6), \
             gre(sw, d, vrf_o,
                 tos="inherit",
                 local_ip="1.2.3.4",
                 remote_ip="1.2.3.7") as g, \
             encap_route(sw, vrf_o, 2, g, ip=ipv4), \
             encap_route(sw, vrf_o, 2, g, ip=ipv6):

            sleep(15)
            ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1, g,
                      count=25, fail_expected=True, ipv6=True)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g,
                      count=25, fail_expected=True)

            sw.run("ip t change name %s remote 1.2.3.5" % g.get_devname())

            sleep(5)
            ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1, g,
                      ipv6=True)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g)

        logging.info("--- local change")
        with encap_route(m2, vrf_None, 1, "gre1", ip=ipv4), \
             encap_route(m2, vrf_None, 1, "gre1", ip=ipv6), \
             gre(sw, d, vrf_o,
                 tos="inherit",
                 local_ip="1.2.3.6",
                 remote_ip="1.2.3.5") as g, \
             encap_route(sw, vrf_o, 2, g, ip=ipv4), \
             encap_route(sw, vrf_o, 2, g, ip=ipv6):

            sleep(15)
            ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1, g,
                      count=25, fail_expected=True, ipv6=True)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g,
                      count=25, fail_expected=True)

            sw.run("ip t change name %s local 1.2.3.4" % g.get_devname())

            sleep(5)
            ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1, g,
                      ipv6=True)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g)

        # IPv4 should go through g4, IPv6 through g6, but g4 starts out
        # misconfigured. Thus there's no conflict and both g4 and g6 are
        # offloaded. When the configuration of g4 is fixed, both tunnels are
        # forced to slow path, but now they both work.
        logging.info("--- local change conflict")
        with encap_route(m2, vrf_None, 1, "gre1", ip=ipv4), \
             dummy(sw, vrf_u, ip=["1.2.3.6/32"]) as d4, \
             gre(sw, d4, vrf_o,
                 tos="inherit",
                 local_ip="1.2.3.6",
                 remote_ip="1.2.3.5") as g4, \
             encap_route(sw, vrf_o, 2, g4, ip=ipv4), \
             \
             encap_route(m2, vrf_None, 1, "gre2", ip=ipv6), \
             gre(sw, d, vrf_o,
                 tos="inherit",
                 local_ip="1.2.3.4",
                 remote_ip="1.2.3.5",
                 ikey=2222, okey=1111) as g6, \
             encap_route(sw, vrf_o, 2, g6, ip=ipv6):

            sleep(15)
            ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1, g6,
                      count=25, ipv6=True)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g4,
                      count=25, fail_expected=True)

            sw.run("ip t change name %s local 1.2.3.4" % g4.get_devname())

            sleep(5)
            ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1, g6,
                      ipv6=True, require_fastpath=False)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g4,
                      require_fastpath=False)

        logging.info("--- ikey change")
        with encap_route(m2, vrf_None, 1, "gre2", ip=ipv4), \
             encap_route(m2, vrf_None, 1, "gre2", ip=ipv6), \
             gre(sw, d, vrf_o,
                 tos="inherit",
                 local_ip="1.2.3.4",
                 remote_ip="1.2.3.5",
                 ikey=2, okey=1111) as g, \
             encap_route(sw, vrf_o, 2, g, ip=ipv4), \
             encap_route(sw, vrf_o, 2, g, ip=ipv6):

            sleep(15)
            ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1, g,
                      count=25, fail_expected=True, ipv6=True)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g,
                      count=25, fail_expected=True)

            sw.run("ip t change name %s ikey 2222" % g.get_devname())

            sleep(5)
            ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1, g,
                      ipv6=True)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g)

        logging.info("--- okey change")
        with encap_route(m2, vrf_None, 1, "gre2", ip=ipv4), \
             encap_route(m2, vrf_None, 1, "gre2", ip=ipv6), \
             gre(sw, d, vrf_o,
                 tos="inherit",
                 local_ip="1.2.3.4",
                 remote_ip="1.2.3.5",
                 ikey=2222, okey=1) as g, \
             encap_route(sw, vrf_o, 2, g, ip=ipv4), \
             encap_route(sw, vrf_o, 2, g, ip=ipv6):

            sleep(15)
            ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1, g,
                      count=25, fail_expected=True, ipv6=True)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g,
                      count=25, fail_expected=True)

            sw.run("ip t change name %s okey 1111" % g.get_devname())

            sleep(5)
            ping_test(tl, m1, sw, ipv6(test_ip(2, 33, [])), m1_if1, g,
                      ipv6=True)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
