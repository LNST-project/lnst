import lnst

m1 = lnst.add_host()
m2 = lnst.add_host()

m1_eth1 = m1.add_interface(label="tnet")
m2_eth1 = m2.add_interface(label="tnet")

while lnst.match():
    m1.sync_resources(modules=["Icmp6Ping", "IcmpPing"])
    m2.sync_resources(modules=["Icmp6Ping", "IcmpPing"])

    lnst.wait(15)

    ipv = lnst.get_alias("ipv", default="ipv4")
    print "ipv"
    print ipv
    mtu = lnst.get_alias("mtu", default="1500")
    print "mtu"
    print mtu

    m1_eth1.reset(ip=["192.168.101.10/24", "fc00:0:0:0::1/64"])
    m2_eth1.reset(ip=["192.168.101.11/24", "fc00:0:0:0::2/64"])

    ping_mod = lnst.get_module("IcmpPing",
                               options={
                                  "addr": m2_eth1.get_ip(0),
                                  "count": 10,
                                  "interval": 0.1,
                                  "iface" : m1_eth1.get_devname(),
                                  "limit_rate": 90})

    ping_mod6 = lnst.get_module("Icmp6Ping",
                               options={
                                  "addr": m2_eth1.get_ip(1),
                                  "count": 10,
                                  "interval": 0.1,
                                  "iface" : m1_eth1.get_devname(),
                                  "limit_rate": 90})

    m1_eth1.set_mtu(mtu)
    m2_eth1.set_mtu(mtu)

    if ipv in [ 'ipv6', 'both' ]:
        m1.run(ping_mod6)

    if ipv in ['ipv4', 'both' ]:
        m1.run(ping_mod)
