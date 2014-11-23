from lnst.Controller.Task import ctl

# ------
# SETUP
# ------

m1 = ctl.get_host("testmachine1")
m2 = ctl.get_host("testmachine2")

m1.sync_resources(modules=["IcmpPing", "Netperf"])
m2.sync_resources(modules=["IcmpPing", "Netperf"])

# ------
# TESTS
# ------

vlans = ["vlan10", "vlan20", "vlan30"]
offloads = ["gso", "gro", "tso"]

for vlan1 in vlans:
    for vlan2 in vlans:
        ping_mod = ctl.get_module("IcmpPing",
                                   options={
                                       "addr" : m2.get_ip(vlan2),
                                       "count" : 100,
                                       "iface" : m1.get_devname(vlan1),
                                       "interval" : 0.1
                                   })
        netperf_srv = ctl.get_module("Netperf",
                                      options={
                                          "role" : "server",
                                          "bind" : m1.get_ip(vlan1),
                                      })
        netperf_cli_tcp = ctl.get_module("Netperf",
                                          options={
                                              "role" : "client",
                                              "netperf_server" :
                                                  m1.get_ip(vlan1),
                                              "duration" : 60,
                                              "testname" : "TCP_STREAM",
                                              "netperf_opts" :
                                                  "-L %s" % m2.get_ip(vlan1)
                                          })
        netperf_cli_udp = ctl.get_module("Netperf",
                                          options={
                                              "role" : "client",
                                              "netperf_server" :
                                                  m1.get_ip(vlan1),
                                              "duration" : 60,
                                              "testname" : "UDP_STREAM",
                                              "netperf_opts" :
                                                  "-L %s" % m2.get_ip(vlan1)
                                          })
        for offload in offloads:
            # These tests should pass
            # Ping between same VLANs
            if vlan1 == vlan2:
                for state in ["on", "off"]:
                # Offload setup
                    m1.run("ethtool -K %s %s %s" % (m1.get_devname("eth1"),
                                                    offload, state))
                    m2.run("ethtool -K %s %s %s" % (m2.get_devname("eth1"),
                                                    offload, state))

                    # Ping test
                    m1.run(ping_mod)

                    # Netperf test (both TCP and UDP)
                    srv_proc = m1.run(netperf_srv, bg=True)
                    ctl.wait(2)
                    m2.run(netperf_cli_tcp, timeout=65)
                    m2.run(netperf_cli_udp, timeout=65)
                    srv_proc.intr()

            # These tests should fail
            # Ping across different VLAN
            elif vlan1 != vlan2:
                for state in ["on", "off"]:
                    # Offload setup
                    m1.run("ethtool -K %s %s %s" % (m1.get_devname("eth1"),
                                                    offload, state))
                    m2.run("ethtool -K %s %s %s" % (m2.get_devname("eth1"),
                                                    offload, state))

                    # Ping test
                    m1.run(ping_mod, expect="fail")
