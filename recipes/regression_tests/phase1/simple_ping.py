from lnst.Controller.Task import ctl

hostA = ctl.get_host("machine1")
hostB = ctl.get_host("machine2")

hostA.sync_resources(modules=["Icmp6Ping", "IcmpPing"])
hostB.sync_resources(modules=["Icmp6Ping", "IcmpPing"])

ping_mod = ctl.get_module("IcmpPing",
                           options={
                              "addr": hostB.get_ip("testiface", 0),
                              "count": 100,
                              "interval": 0.2,
                              "iface" : hostA.get_devname("testiface"),
                              "limit_rate": 90})

ping_mod6 = ctl.get_module("Icmp6Ping",
                           options={
                              "addr": hostB.get_ip("testiface", 1),
                              "count": 100,
                              "interval": 0.2,
                              "iface" : hostA.get_ip("testiface", 1),
                              "limit_rate": 90})

ctl.wait(15)

ipv = ctl.get_alias("ipv")
mtu = ctl.get_alias("mtu")

test_if1 = hostA.get_interface("testiface")
test_if1.set_mtu(mtu)
test_if2 = hostB.get_interface("testiface")
test_if2.set_mtu(mtu)


if ipv in [ 'ipv6', 'both' ]:
    hostA.run(ping_mod6)

if ipv in [ 'ipv4', 'both' ]:
    hostA.run(ping_mod)
