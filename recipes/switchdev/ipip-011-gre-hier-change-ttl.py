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
    m1_if1, m2_if1, m2_mg, m2_v3, sw_if1, sw_if2 = ifaces

    m2.config("/proc/sys/net/ipv4/ip_forward", "1", netns="ns1")
    m2.config("/proc/sys/net/ipv4/ip_forward", "1", netns="ns2")

    m1_if1.add_nhs_route(ipv4(test_ip(2, 0)), [ipv4(test_ip(1, 1, []))])
    m1_if1.add_nhs_route(ipv6(test_ip(2, 0)), [ipv6(test_ip(1, 1, []))])
    m2_if1.add_nhs_route("1.2.3.4/32", [ipv4(test_ip(99, 1, []))])
    m2_if1.add_nhs_route("1.2.3.5/32", [ipv4(test_ip(88, 2, []))])
    m2_v3.add_nhs_route("1.2.3.4/32", [ipv4(test_ip(88, 1, []))])
    m2_v3.add_nhs_route("1.2.3.5/32", [ipv4(test_ip(77, 2, []))])
    m2_mg.add_nhs_route("1.2.3.4/32", [ipv4(test_ip(77, 1, []))])

    vrf_None = None
    tl = TestLib(ctl, aliases)

    logging.info("=== TTL tests")
    with vrf(sw) as vrf_u, \
         vrf(sw) as vrf_o, \
         dummy(sw, vrf_u, ip=["1.2.3.4/32"]) as d, \
         encap_route(m2, vrf_None, 1, "mg", ip=ipv4), \
         encap_route(m2, vrf_None, 1, "mg", ip=ipv6):
        connect_host_ifaces(sw, sw_if1, vrf_o, sw_if2, vrf_u)
        sw_if1.reset()
        sw_if2.reset()
        add_forward_route(sw, vrf_u, "1.2.3.5", via=ipv4(test_ip(99, 2, [])))

        # - Test that tunnel configured with TTL inherit actually copies the TTL
        #   from the overlay packet. The topology is as follows:
        #
        #    +-- M1 ----------------+             +-- M2 ----------------+
        #    |           1.33/24 +--|----.        |                      |
        #    |                      |    |        |        2.33/32 md +  |
        #    +----------------------+    |        |     1.2.3.5/31 mg +  |
        #    +-- SW -------------------------+    |   + 77.2             |
        #    |                           |   |    |   |                  |
        #    | +-- ol vrf -----------------+ |    | +-- ns2 -----------+ |
        #    | | 1.2.3.4/31 g +          | | |    | | |         88.2 + | |
        #    | |              |   1.1/24 + | |    | | + 77.1         | | |
        #    | +---------------------------+ |    | +------------------+ |
        #    |                |              |    |                  |   |
        #    | +-- ul vrf -----------------+ |    | +-- ns1 -----------+ |
        #    | |              |         +--|-|----|-|--+             | | |
        #    | | 1.2.3.4/32 d +    99.1/24 | |    | | 99.2/24   88.1 + | |
        #    | +---------------------------+ |    | +------------------+ |
        #    +-------------------------------+    +----------------------+
        #
        #   The point of the test is that there are several next hops between
        #   1.2.3.4 and 1.2.3.5. If the tunnel is set to "ttl inherit", ping
        #   with TTL of 3 (ping -t 3) never reaches the other endpoint, but ping
        #   with TTL of 4 does.
        with dummy(sw, vrf_u) as d, \
             gre(sw, d, vrf_o,
                 tos="inherit",
                 local_ip="1.2.3.4",
                 remote_ip="1.2.3.5") as g, \
             encap_route(sw, vrf_o, 2, g, ip=ipv4), \
             encap_route(sw, vrf_o, 2, g, ip=ipv6):

            logging.info("--- TTL inherit")

            sleep(15)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g,
                      count=25, ttl=3, fail_expected=True)

            sleep(5)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g, ttl=4)

            # - On the same topology, after offloading a tunnel with "ttl
            #   inherit", set the tunnel to e.g. "ttl 64". Now the other
            #   endpoint should become reachable again even with ping -t 3. Thus
            #   we know that the tunnel was moved to slow path correcly (or the
            #   TTL was reflected in the hardware, we don't care).

            logging.info("--- ip t change ttl")
            sw.run("ip t change name %s ttl 64" % g.get_devname())

            sleep(5)
            ping_test(tl, m1, sw, ipv4(test_ip(2, 33, [])), m1_if1, g,
                      ttl=3, require_fastpath=False)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("machine2").get_interface("mg"),
         ctl.get_host("machine2").get_interface("v3"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
