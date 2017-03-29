from lnst.Controller.Task import ctl

# ------
# SETUP
# ------

h1 = ctl.get_host("host1")
g1 = ctl.get_host("guest1")
h2 = ctl.get_host("host2")

g1.sync_resources(modules=["IcmpPing", "Icmp6Ping"])
h2.sync_resources(modules=["IcmpPing", "Icmp6Ping"])

# ------
# TESTS
# ------

ipv = ctl.get_alias("ipv")
h2_vlan10 = h2.get_interface("vlan10")
g1_vlan10 = g1.get_interface("vlan10")

ping_count = 100
ping_interval = 0.2

ping_mod = ctl.get_module("IcmpPing",
                           options={
                               "addr": h2_vlan10.get_ip(0),
                               "count": ping_count,
                               "iface": g1_vlan10.get_devname(),
                               "interval": ping_interval
                           })

ping_mod6 = ctl.get_module("Icmp6Ping",
                           options={
                               "addr": h2_vlan10.get_ip(1),
                               "count": ping_count,
                               "iface": g1_vlan10.get_ip(1),
                               "interval": ping_interval
                           })

p_opts = "-L %s" % (h2_vlan10.get_ip(0))
p_opts6 = "-L %s -6" % (h2_vlan10.get_ip(1))

if ipv in ('ipv4', 'both'):
    g1.run(ping_mod)

if ipv in ('ipv6', 'both'):
    g1.run(ping_mod6)
