import lnst

# if1 ... src
# if2 ... dst
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
m1_eth2 = m1.add_interface(label="tnet")
m2_eth1 = m2.add_interface(label="tnet")

while lnst.match():
    m1.sync_resources(modules=["IcmpPing"])
    m2.sync_resources(modules=["IcmpPing"])
    m2_eth1.reset(ip="192.168.0.2/24")
    ping = ping_mod_init(m1_eth1, m2_eth1)
    #lnst.breakpoint()
    team_if = m1.create_team(slaves=[m1_eth1, m1_eth2])
    #lnst.breakpoint()
    team_if.reset(ip="192.168.0.1/24")
    #lnst.breakpoint()
    ping = ping_mod_init(team_if, m2_eth1)
    #lnst.breakpoint()
    m1.run(ping)
