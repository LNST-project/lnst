"""
Copyright 2016 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
yotamg@mellanox.com (Yotam Gigi)
"""

from lnst.Controller.Task import ctl
from TestLib import TestLib
from time import sleep

ROUTES_COUNT = 5000
PKTGEN_COUNT = 10000

MAJOR_MIN = 10
MINOR_MIN = 1
MINOR_MAX = 254
MINORS_TOTAL = MINOR_MAX - MINOR_MIN + 1

def test_ip(major, minor, prefix=[24,64]):
    return ["192.168.%d.%d%s" % (major, minor,
            "/" + str(prefix[0]) if len(prefix) > 0 else ""),
            "2002:%d::%d%s" % (major, minor,
            "/" + str(prefix[1]) if len(prefix) > 1 else "")]

def ipv4(test_ip):
    return test_ip[0]

def get_route_minor(route_index):
    return MINOR_MIN + route_index % MINORS_TOTAL

def get_route_major(route_index):
    return MAJOR_MIN + route_index / MINORS_TOTAL

def get_all_route_majors():
    return range(get_route_major(0), get_route_major(ROUTES_COUNT - 1) + 1)

def get_route_major_minor_range(major):
    minor_min = MINOR_MIN

    last_major = get_route_major(ROUTES_COUNT - 1)
    if major == last_major:
        minor_max = get_route_minor(ROUTES_COUNT - 1)
    else:
        minor_max = MINOR_MAX

    return minor_min, minor_max

def traffic_route_major(tl, major, if_from, if_to, if_through):
    """
    Run traffic from if_from to if_to, where the destination MAC address is the
    MAC address of if_through, and where the traffic is destined to all
    available IP addresses for the specific major. For example, for major 12,
    the traffic will be ran with dst_ip = 192.168.12.[1..254]

    The function returns the number of packets sent.
    """
    minor_min, minor_max = get_route_major_minor_range(major)
    tl.pktgen(if_from, if_to, 100, dst_mac = if_through.get_hwaddr(),
              count = PKTGEN_COUNT, rate = "10MB",
              dst_min = ipv4(test_ip(major, minor_min, [])),
              dst_max = ipv4(test_ip(major, minor_max, [])))

    return PKTGEN_COUNT

def do_task(ctl, hosts, ifaces, aliases):
    """
    This test deffines MAX_ROUTES number of routes on the switch with different
    32bit prefixes in the range 192.168.[10..].[1..254] and redirects them to a
    nexthop on machine2. The test than checks that:
     - All routes has the offloaded flag
     - Traffic destined to each of the route prefixes did end up on machine2, as
       the route specifies
    """
    m1, sw, m2 = hosts
    m1_if1, sw_if1, sw_if2, m2_if1 = ifaces

    m1_if1.reset(ip=test_ip(1, 1))
    sw_if1.reset(ip=test_ip(1, 2))

    sw_if2.reset(ip=test_ip(2, 2))
    m2_if1.reset(ip=test_ip(2, 3))

    for route_index in range(ROUTES_COUNT):
        route_major = get_route_major(route_index)
        route_minor = get_route_minor(route_index)
        sw_if1.add_nhs_route(ipv4(test_ip(route_major, route_minor, [])),
                             [ipv4(test_ip(2, 3, []))])

    sleep(30)
    tl = TestLib(ctl, aliases)

    # check that there are ROUTES_COUNT offloaded routes
    dc_routes, nh_routes = sw.get_routes()
    offloaded_routes_num = 0
    for nh_route in nh_routes:
        if "offload" in nh_route["nexthops"][0]["flags"]:
            offloaded_routes_num += 1

    if offloaded_routes_num < ROUTES_COUNT:
        tl.custom(sw, "route", "Only %d out of %d routes offloaded" %
                  (offloaded_routes_num, ROUTES_COUNT))

    # run traffic, and validate that each route will be hit
    sleep(2)
    before_stats = m2_if1.link_stats()["rx_packets"]

    total_sent = 0
    for major in get_all_route_majors():
        total_sent += traffic_route_major(tl, major, m1_if1, m2_if1, sw_if1)

    sleep(2)
    after_stats = m2_if1.link_stats()["rx_packets"]
    recieved = after_stats - before_stats

    # validate that all traffic went according to the routes
    thresh = total_sent * 0.95
    if recieved < thresh:
        tl.custom(sw, "route", "Recieved %d out of %d packets" %
                  (recieved, thresh))

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("switch"),
              ctl.get_host("machine2")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2"),
         ctl.get_host("machine2").get_interface("if1")],
        ctl.get_aliases())
