from lnst.Controller.Task import ctl
from Testlib import Testlib

# ------
# SETUP
# ------

tl = Testlib(ctl)

h1 = ctl.get_host("host1")
g1 = ctl.get_host("guest1")
g2 = ctl.get_host("guest2")

g1.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Iperf"])
g2.sync_resources(modules=["Iperf"])

# ------
# TESTS
# ------

ipv = ctl.get_alias("ipv")
do_iperf = ctl.get_alias("iperf")

g1_guestnic = g1.get_interface("if1")
g1_mac = g1_guestnic.get_hwaddr()
g2_guestnic = g2.get_interface("if1")
g2_mac = g2_guestnic.get_hwaddr()

ping_count = 30
ping_interval = 0.2
ping_timeout = 10

def ping(options={}):
    options = dict(options)
    options.update({
       "addr": g2_guestnic.get_ip(0),
       "count": ping_count,
       "iface": g1_guestnic.get_devname(),
       "interval": ping_interval
    })
    ping_mod = ctl.get_module("IcmpPing", options=options)
    g1.run(ping_mod, timeout=ping_timeout)


def ping6(options={}):
    options = dict(options)
    options.update({
        "addr": g2_guestnic.get_ip(1),
        "count": ping_count,
        "iface": g1_guestnic.get_ip(1),
        "interval": ping_interval
    })
    ping_mod6 = ctl.get_module("Icmp6Ping", options=options)
    g1.run(ping_mod6, timeout=ping_timeout)


def verify_tc_rules(proto):
    m = tl.find_tc_rule(h1, 'tap1', g1_mac, g2_mac, proto, 'mirred')
    if m:
        tl.custom(h1, "TC rule %s vm1->vm2" % proto, opts=m)
    else:
        tl.custom(h1, "TC rule %s vm1->vm2" % proto, 'ERROR: cannot find tc rule')

    m = tl.find_tc_rule(h1, 'tap2', g2_mac, g1_mac, proto, 'mirred')
    if m:
        tl.custom(h1, "TC rule %s vm2->vm1" % proto, opts=m)
    else:
        tl.custom(h1, "TC rule %s vm2->vm1" % proto, 'ERROR: cannot find tc rule')


if ipv in ('ipv4', 'both'):
    ping()
    verify_tc_rules('ip')
    for size in (200, 400, 1000):
        ping({'size': size})

if ipv in ('ipv6', 'both'):
    ping6()
    verify_tc_rules('ipv6')
    for size in (200, 400, 1000):
        ping6({'size': size})

if do_iperf:
    tl.iperf(g1_guestnic, g2_guestnic, 30, 'vm1->vm2')
