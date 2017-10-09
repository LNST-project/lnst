"""
A helper module for IP-in-IP tests.

Copyright 2017 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
petrm@mellanox.com (Petr Machata)
"""

from lnst.Controller.Task import ctl
from TestLib import route

def ping_test(tl, m1, sw, addr, m1_if1, gre,
              require_fastpath=True, fail_expected=False, count=100,
              ipv6=False):
    limit = int(0.9 * count)
    if gre is not None:
        before_stats = gre.link_stats()["rx_packets"]
    ping_mod = ctl.get_module("IcmpPing" if not ipv6 else "Icmp6Ping",
                                options={
                                    "addr": addr,
                                    "count": count,
                                    "interval": 0.2,
                                    "iface" : m1_if1.get_devname(),
                                    "limit_rate": limit,
                                })
    m1.run(ping_mod, fail_expected=fail_expected)

    if not fail_expected and gre is not None:
        after_stats = gre.link_stats()["rx_packets"]

        delta = after_stats - before_stats
        if require_fastpath and delta > 10:
            # Allow a few packets of control plane traffic to go through slow
            # path. All the data plane traffic should go through fast path.
            tl.custom(sw, "ipip",
                      "Too many packets (%d) observed at GRE netdevice" % delta)

def ipv4(test_ip):
    return test_ip[0]

def ipv6(test_ip):
    return test_ip[1]

def encap_route(m, vrf, subnet, if_or_name, ip=ipv4, src=None):
    if type(if_or_name) is str:
        devname = m.get_interface(if_or_name).get_devname()
    else:
        devname = if_or_name.get_devname()
    if src is not None:
        srcstr = " src %s" % src
    else:
        srcstr = ""
    return route(m, vrf, "%s dev %s%s" %
                 (ip(test_ip(subnet, 0)), devname, srcstr))

def test_ip(major, minor, prefix=[24,64]):
    return ["192.168.%d.%d%s" % (major, minor,
            "/" + str(prefix[0]) if len(prefix) > 0 else ""),
            "2002:%d::%d%s" % (major, minor,
            "/" + str(prefix[1]) if len(prefix) > 1 else "")]

def add_forward_route(m, vrf, remote_ip, via=ipv4(test_ip(99, 2, []))):
    route(m, vrf, "%s/32 via %s"
          % (remote_ip, via)).__enter__()

def connect_host_ifaces(sw, if_o, vrf_o, if_u, vrf_u):
    sw.run("ip l set dev %s master %s" % (if_o.get_devname(), vrf_o))
    sw.run("ip l set dev %s master %s" % (if_u.get_devname(), vrf_u))
