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
                              "iface" : hostA.get_ip("testiface"),
                              "limit_rate": 90})

if ctl.get_alias('ipv') == 'ipv6':
    hostA.run(ping_mod6)

elif ctl.get_alias('ipv') == 'ipv4':
    hostA.run(ping_mod)

else:
    hostA.run(ping_mod)
    hostA.run(ping_mod6)
