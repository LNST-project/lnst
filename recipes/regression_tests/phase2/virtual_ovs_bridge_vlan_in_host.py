from lnst.Controller.Task import ctl

# ------
# SETUP
# ------

h1 = ctl.get_host("host1")
g1 = ctl.get_host("guest1")

h2 = ctl.get_host("host2")

g1.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Netperf"])
h2.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Netperf"])

# ------
# TESTS
# ------

offloads = ["gso", "gro", "tso"]

ipv = ctl.get_alias("ipv")

ping_mod = ctl.get_module("IcmpPing",
                           options={
                               "addr" : h2.get_ip("vlan10"),
                               "count" : 100,
                               "iface" : g1.get_devname("guestnic"),
                               "interval" : 0.1
                           })

ping_mod6 = ctl.get_module("Icmp6Ping",
                           options={
                               "addr" : h2.get_ip("vlan10", 1),
                               "count" : 100,
                               "iface" : g1.get_ip("guestnic", 1),
                               "interval" : 0.1
                           })

netperf_srv = ctl.get_module("Netperf",
                              options={
                                  "role" : "server",
                                  "bind" : g1.get_ip("guestnic")
                              })

netperf_srv6 = ctl.get_module("Netperf",
                              options={
                                  "role" : "server",
                                  "bind" : g1.get_ip("guestnic", 1),
                                  "netperf_opts" : " -6",
                              })

netperf_cli_tcp = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" : g1.get_ip("guestnic"),
                                      "duration" : 60,
                                      "testname" : "TCP_STREAM",
                                      "netperf_opts" : "-L %s" %
                                                            h2.get_ip("vlan10")
                                  })

netperf_cli_udp = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" : g1.get_ip("guestnic"),
                                      "duration" : 60,
                                      "testname" : "UDP_STREAM",
                                      "netperf_opts" : "-L %s" %
                                                            h2.get_ip("vlan10")
                                  })

netperf_cli_tcp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" :
                                          g1.get_ip("guestnic", 1),
                                      "duration" : 60,
                                      "testname" : "TCP_STREAM",
                                      "netperf_opts" :
                                          "-L %s -6" % h2.get_ip("vlan10", 1)
                                  })

netperf_cli_udp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" :
                                          g1.get_ip("guestnic", 1),
                                      "duration" : 60,
                                      "testname" : "UDP_STREAM",
                                      "netperf_opts" :
                                          "-L %s -6" % h2.get_ip("vlan10", 1)
                                  })
ctl.wait(15)

for offload in offloads:
    for state in ["off", "on"]:
            h1.run("ethtool -K %s %s %s" % (h1.get_devname("nic"),
                                            offload, state))
            g1.run("ethtool -K %s %s %s" % (g1.get_devname("guestnic"),
                                            offload, state))
            h2.run("ethtool -K %s %s %s" % (h2.get_devname("nic"),
                                            offload, state))
            if ipv == 'ipv4':
                g1.run(ping_mod)
                server_proc = g1.run(netperf_srv, bg=True)
                ctl.wait(2)
                h2.run(netperf_cli_tcp, timeout=65)
                h2.run(netperf_cli_udp, timeout=65)
                server_proc.intr()

            elif ipv == 'ipv6':
                g1.run(ping_mod6)
                server_proc = g1.run(netperf_srv6, bg=True)
                ctl.wait(2)
                h2.run(netperf_cli_tcp6, timeout=65)
                h2.run(netperf_cli_udp6, timeout=65)
                server_proc.intr()

            else:
                g1.run(ping_mod)
                server_proc = g1.run(netperf_srv, bg=True)
                ctl.wait(2)
                h2.run(netperf_cli_tcp, timeout=65)
                h2.run(netperf_cli_udp, timeout=65)
                server_proc.intr()

                g1.run(ping_mod6)
                server_proc = g1.run(netperf_srv6, bg=True)
                ctl.wait(2)
                h2.run(netperf_cli_tcp6, timeout=65)
                h2.run(netperf_cli_udp6, timeout=65)
                server_proc.intr()
