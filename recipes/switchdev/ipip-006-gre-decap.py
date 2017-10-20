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

def refresh_addrs(m, iface):
    # A device loses IPv6 address when changing VRF, which we normally work
    # around with doing a reset of the device. But for VLAN devices, reset
    # removes and recreates them in default VRF. So instead reset the addresses
    # by hand.
    m.run("ip a flush dev %s" % iface.get_devname())

    # Down/up cycle to get a new link-local address so that IPv6 neighbor
    # discovery works.
    m.run("ip l set dev %s down" % iface.get_devname())
    m.run("ip l set dev %s up" % iface.get_devname())

    # Now reassign the fixed addresses.
    for ip, mask in iface.get_ips().get_val():
        m.run("ip a add dev %s %s/%s" % (iface.get_devname(), ip, mask))

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    (m1_if1_10, m1_if1_20,
     m2_if1_10, m2_if1_20,
     sw_if1_10, sw_if1_20,
     sw_if2_10, sw_if2_20) = ifaces

    m2_if1_10.add_nhs_route("1.2.3.4/32", [ipv4(test_ip(99, 1, []))])

    vrf_None = None
    tl = TestLib(ctl, aliases)

    logging.info("=== Decap-only flow in default VRF")
    with encap_route(m2, vrf_None, 1, "gre1",
                     ip=ipv4, src=ipv4(test_ip(2, 33, []))), \
         encap_route(m2, vrf_None, 1, "gre1", ip=ipv6), \
         dummy(sw, vrf_None, ip=["1.2.3.4/32"]) as d, \
         gre(sw, None, vrf_None,
             tos="inherit",
             local_ip="1.2.3.4",
             remote_ip="1.2.3.5") as g:

        add_forward_route(sw, vrf_None, "1.2.3.5")
        sleep(15)

        ping_test(tl, m2, sw, ipv6(test_ip(1, 33, [])), m2_if1_10, g, ipv6=True)
        ping_test(tl, m2, sw, ipv4(test_ip(1, 33, [])), m2_if1_10, g)

    logging.info("=== Decap-only flow in hierarchical configuration")
    with encap_route(m2, vrf_None, 1, "gre1",
                     ip=ipv4, src=ipv4(test_ip(2, 33, []))), \
         encap_route(m2, vrf_None, 1, "gre1", ip=ipv6), \
         vrf(sw) as vrf_u, \
         vrf(sw) as vrf_o, \
         dummy(sw, vrf_u, ip=["1.2.3.4/32"]) as d, \
         gre(sw, d, vrf_o,
             tos="inherit",
             local_ip="1.2.3.4",
             remote_ip="1.2.3.5") as g:

        connect_host_ifaces(sw, sw_if1_10, vrf_o, sw_if2_10, vrf_u)
        refresh_addrs(sw, sw_if1_10)
        add_forward_route(sw, vrf_u, "1.2.3.5")

        ping_test(tl, m2, sw, ipv6(test_ip(1, 33, [])), m2_if1_10, g, ipv6=True)
        ping_test(tl, m2, sw, ipv4(test_ip(1, 33, [])), m2_if1_10, g)

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
