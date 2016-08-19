import lnst

def ping_mod_init(if1, if2):
    ping_mod = lnst.get_module("IcmpPing",
                               options={
                                  "addr": if2.get_ip(0),
                                  "count": 10,
                                  "interval": 1,
                                  "iface" : if1.get_devname()})
    return ping_mod

m1 = lnst.add_host()
m2 = lnst.add_host()

m1_eth1 = m1.add_interface(label="tnet")
m2_eth1 = m2.add_interface(label="tnet")

while lnst.match():
    m1.sync_resources(modules=["IcmpPing"])
    m2.sync_resources(modules=["IcmpPing"])

    m1_vlan10 = m1.create_vlan(realdev_iface=m1_eth1, vlan_tci="10", ip="192.168.10.1/24")
    m1_vlan20 = m1.create_vlan(realdev_iface=m1_eth1, vlan_tci="20", ip="192.168.20.1/24")
    m1_vlan30 = m1.create_vlan(realdev_iface=m1_eth1, vlan_tci="30", ip="192.168.30.1/24")

    m2_vlan10 = m2.create_vlan(realdev_iface=m2_eth1, vlan_tci="10", ip="192.168.10.2/24")
    m2_vlan20 = m2.create_vlan(realdev_iface=m2_eth1, vlan_tci="20", ip="192.168.20.2/24")
    m2_vlan30 = m2.create_vlan(realdev_iface=m2_eth1, vlan_tci="30", ip="192.168.30.2/24")

    ping_mod = ping_mod_init(m1_vlan10, m2_vlan10)
    ping_mod_bad = ping_mod_init(m1_vlan10, m2_vlan20)

    m1.run(ping_mod)
    #m1.run(ping_mod_bad)
