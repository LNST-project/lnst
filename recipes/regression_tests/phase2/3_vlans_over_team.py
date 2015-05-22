from lnst.Controller.Task import ctl

# ------
# SETUP
# ------

m1 = ctl.get_host("testmachine1")
m2 = ctl.get_host("testmachine2")

m1.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Netperf"])
m2.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Netperf"])

# ------
# TESTS
# ------

vlans = ["vlan10", "vlan20", "vlan30"]
offloads = ["gso", "gro", "tso"]

ipv = ctl.get_alias('ipv')
mtu = ctl.get_alias('mtu')

m1_team = m1.get_interface("test_if")
m1_team.set_mtu(mtu)
m2_phy1 = m2.get_interface("eth1")
m2_phy1.set_mtu(mtu)

for vlan in vlans:
    vlan_if1 = m1.get_interface(vlan)
    vlan_if1.set_mtu(mtu)
    vlan_if2 = m2.get_interface(vlan)
    vlan_if2.set_mtu(mtu)


ctl.wait(15)

for vlan1 in vlans:
    for vlan2 in vlans:
        ping_mod = ctl.get_module("IcmpPing",
                                   options={
                                       "addr" : m2.get_ip(vlan2, 0),
                                       "count" : 100,
                                       "iface" : m1.get_devname(vlan1),
                                       "interval" : 0.1
                                   })

        ping_mod6 = ctl.get_module("Icmp6Ping",
                                   options={
                                       "addr" : m2.get_ip(vlan2, 1),
                                       "count" : 100,
                                       "iface" : m1.get_ip(vlan1, 1),
                                       "interval" : 0.1
                                   })

        netperf_srv = ctl.get_module("Netperf",
                                      options={
                                          "role" : "server",
                                          "bind" : m1.get_ip(vlan1, 0),
                                      })

        netperf_srv6 = ctl.get_module("Netperf",
                                      options={
                                          "role" : "server",
                                          "bind" : m1.get_ip(vlan1, 1),
                                          "netperf_opts" : " -6",
                                      })

        netperf_cli_tcp = ctl.get_module("Netperf",
                                          options={
                                              "role" : "client",
                                              "netperf_server" :
                                                  m1.get_ip(vlan1, 0),
                                              "duration" : 60,
                                              "testname" : "TCP_STREAM",
                                              "netperf_opts" :
                                                  "-L %s" % m2.get_ip(vlan1, 0)
                                          })

        netperf_cli_udp = ctl.get_module("Netperf",
                                          options={
                                              "role" : "client",
                                              "netperf_server" :
                                                  m1.get_ip(vlan1, 0),
                                              "duration" : 60,
                                              "testname" : "UDP_STREAM",
                                              "netperf_opts" :
                                                  "-L %s" % m2.get_ip(vlan1, 0)
                                          })

        netperf_cli_tcp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" :
                                          m1.get_ip(vlan1, 1),
                                      "duration" : 60,
                                      "testname" : "TCP_STREAM",
                                      "netperf_opts" :
                                          "-L %s -6" % m2.get_ip(vlan1, 1)
                                  })
        netperf_cli_udp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" :
                                          m1.get_ip(vlan1, 1),
                                      "duration" : 60,
                                      "testname" : "UDP_STREAM",
                                      "netperf_opts" :
                                          "-L %s -6" % m2.get_ip(vlan1, 1)
                                  })

        if vlan1 == vlan2:
            # These tests should pass
            # Ping between same VLANs
            for offload in offloads:
                for state in ["off", "on"]:
                # Offload setup
                    m1.run("ethtool -K %s %s %s" % (m1.get_devname("eth1"),
                                                    offload, state))
                    m1.run("ethtool -K %s %s %s" % (m1.get_devname("eth2"),
                                                    offload, state))
                    m1.run("ethtool -K %s %s %s" % (m1.get_devname("eth3"),
                                                    offload, state))
                    m2.run("ethtool -K %s %s %s" % (m2.get_devname("eth1"),
                                                    offload, state))

                    if ipv in [ 'ipv4', 'both' ]:
                        # Ping test
                        m1.run(ping_mod)

                        # Netperf test (both TCP and UDP)
                        srv_proc = m1.run(netperf_srv, bg=True)
                        ctl.wait(2)
                        m2.run(netperf_cli_tcp, timeout=70)
                        m2.run(netperf_cli_udp, timeout=70)
                        srv_proc.intr()

                    if ipv in [ 'ipv6', 'both' ]:
                        m1.run(ping_mod6)

                        # Netperf test (both TCP and UDP)
                        srv_proc = m1.run(netperf_srv6, bg=True)
                        ctl.wait(2)
                        m2.run(netperf_cli_tcp6, timeout=70)
                        m2.run(netperf_cli_udp6, timeout=70)
                        srv_proc.intr()

        # These tests should fail
        # Ping across different VLAN
        else:
            if ipv in [ 'ipv4', 'both' ]:
                m1.run(ping_mod, expect="fail")

            if ipv in [ 'ipv6', 'both' ]:
                m1.run(ping_mod6, expect="fail")
