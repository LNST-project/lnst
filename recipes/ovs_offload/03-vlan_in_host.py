from lnst.Controller.Task import ctl
from Testlib import Testlib

# ------
# SETUP
# ------

tl = Testlib(ctl)

h1 = ctl.get_host("host1")
g1 = ctl.get_host("guest1")
h2 = ctl.get_host("host2")

g1.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Iperf"])
h2.sync_resources(modules=["Iperf"])

# ------
# TESTS
# ------

ipv = ctl.get_alias("ipv")
do_iperf = ctl.get_alias("iperf")

h2_vlan10 = h2.get_interface("vlan10")
h2_mac = h2_vlan10.get_hwaddr()
g1_guestnic = g1.get_interface("guestnic")
g1_mac = g1_guestnic.get_hwaddr()

ping_count = 100
ping_interval = 0.2

ping_mod = ctl.get_module("IcmpPing",
                           options={
                               "addr": h2_vlan10.get_ip(0),
                               "count": ping_count,
                               "iface": g1_guestnic.get_devname(),
                               "interval": ping_interval
                           })

ping_mod6 = ctl.get_module("Icmp6Ping",
                           options={
                               "addr": h2_vlan10.get_ip(1),
                               "count": ping_count,
                               "iface": g1_guestnic.get_ip(1),
                               "interval": ping_interval
                           })


def verify_tc_rules(proto):
    m = tl.find_tc_rule(h1, 'tap', g1_mac, h2_mac, proto, 'vlan push')
    if m:
        tl.custom(h1, "TC rule %s vlan push" % proto)
    else:
        tl.custom(h1, "TC rule %s vlan push" % proto, 'ERROR: cannot find tc rule')

    m = tl.find_tc_rule(h1, 'nic', h2_mac, g1_mac, '802.1Q', 'vlan pop')
    if m:
        tl.custom(h1, "TC rule %s vlan pop" % proto)
    else:
        tl.custom(h1, "TC rule %s vlan pop" % proto, 'ERROR: cannot find tc rule')


if ipv in ('ipv4', 'both'):
    g1.run(ping_mod)
    verify_tc_rules('ip')

if ipv in ('ipv6', 'both'):
    g1.run(ping_mod6)
    verify_tc_rules('ipv6')

if do_iperf:
    tl.iperf(g1_guestnic, h2_vlan10, 100, 'vm1->h2')
