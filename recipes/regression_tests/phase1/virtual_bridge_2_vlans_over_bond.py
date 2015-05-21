from lnst.Controller.Task import ctl

# ------
# SETUP
# ------

# Host 1 + guests 1 and 2
h1 = ctl.get_host("host1")
g1 = ctl.get_host("guest1")
g1.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Netperf"])
g2 = ctl.get_host("guest2")
g2.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Netperf"])

# Host 2 + guests 3 and 4
h2 = ctl.get_host("host2")
g3 = ctl.get_host("guest3")
g3.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Netperf"])
g4 = ctl.get_host("guest4")
g4.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Netperf"])

# ------
# TESTS
# ------

offloads = ["gso", "gro", "tso"]

ipv = ctl.get_alias("ipv")

ping_mod = ctl.get_module("IcmpPing",
                           options={
                               "addr" : g3.get_ip("guestnic", 0),
                               "count" : 100,
                               "iface" : g1.get_devname("guestnic"),
                               "interval" : 0.1
                           })
ping_mod2 = ctl.get_module("IcmpPing",
                           options={
                               "addr" : g2.get_ip("guestnic", 0),
                               "count" : 100,
                               "iface" : g4.get_ip("guestnic"),
                               "interval" : 0.1
                           })

ping_mod6 = ctl.get_module("Icmp6Ping",
                           options={
                               "addr" : g3.get_ip("guestnic", 1),
                               "count" : 100,
                               "iface" : g1.get_devname("guestnic"),
                               "interval" : 0.1
                           })

ping_mod62 = ctl.get_module("Icmp6Ping",
                           options={
                               "addr" : g2.get_ip("guestnic", 1),
                               "count" : 100,
                               "iface" : g4.get_devname("guestnic"),
                               "interval" : 0.1
                           })

netperf_srv = ctl.get_module("Netperf",
                              options={
                                  "role": "server",
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
                                                          g3.get_ip("guestnic")
                                  })

netperf_cli_udp = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" : g1.get_ip("guestnic"),
                                      "duration" : 60,
                                      "testname" : "UDP_STREAM",
                                      "netperf_opts" : "-L %s" %
                                                          g3.get_ip("guestnic")
                                  })

netperf_cli_tcp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" :
                                          g1.get_ip("guestnic", 1),
                                      "duration" : 60,
                                      "testname" : "TCP_STREAM",
                                      "netperf_opts" :
                                          "-L %s -6" % g3.get_ip("guestnic", 1)
                                  })

netperf_cli_udp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" :
                                          g1.get_ip("guestnic", 1),
                                      "duration" : 60,
                                      "testname" : "UDP_STREAM",
                                      "netperf_opts" :
                                          "-L %s -6" % g3.get_ip("guestnic", 1)
                                  })

ping_mod_bad = ctl.get_module("IcmpPing",
                               options={
                                   "addr" : g4.get_ip("guestnic"),
                                   "count" : 100,
                                   "iface" : g1.get_devname("guestnic"),
                                   "interval" : 0.1
                               })

ping_mod_bad2 = ctl.get_module("IcmpPing",
                               options={
                                   "addr" : g2.get_ip("guestnic"),
                                   "count" : 100,
                                   "iface" : g3.get_devname("guestnic"),
                                   "interval" : 0.1
                               })

ping_mod6_bad = ctl.get_module("Icmp6Ping",
                           options={
                               "addr" : g4.get_ip("guestnic", 1),
                               "count" : 100,
                               "iface" : g1.get_devname("guestnic"),
                               "interval" : 0.1
                           })

ping_mod6_bad2 = ctl.get_module("Icmp6Ping",
                           options={
                               "addr" : g2.get_ip("guestnic", 1),
                               "count" : 100,
                               "iface" : g3.get_devname("guestnic"),
                               "interval" : 0.1
                           })

ctl.wait(15)

for offload in offloads:
    for state in ["off", "on"]:
        h1.run("ethtool -K %s %s %s" % (h1.get_devname("nic1"),
                                        offload, state))
        h1.run("ethtool -K %s %s %s" % (h1.get_devname("nic2"),
                                        offload, state))
        h2.run("ethtool -K %s %s %s" % (h2.get_devname("nic1"),
                                        offload, state))
        h2.run("ethtool -K %s %s %s" % (h2.get_devname("nic2"),
                                        offload, state))
        g1.run("ethtool -K %s %s %s" % (g1.get_devname("guestnic"),
                                        offload, state))
        g2.run("ethtool -K %s %s %s" % (g2.get_devname("guestnic"),
                                        offload, state))
        g3.run("ethtool -K %s %s %s" % (g3.get_devname("guestnic"),
                                        offload, state))
        g4.run("ethtool -K %s %s %s" % (g4.get_devname("guestnic"),
                                        offload, state))
        if ipv == 'ipv4':
            g1.run(ping_mod)
            g4.run(ping_mod2)
            g1.run(ping_mod_bad, expect="fail")
            g3.run(ping_mod_bad2, expect="fail")

            server_proc = g1.run(netperf_srv, bg=True)
            ctl.wait(2)
            g3.run(netperf_cli_tcp, timeout=70)
            g3.run(netperf_cli_udp, timeout=70)
            server_proc.intr()
        elif ipv == 'ipv6':
            g1.run(ping_mod6)
            g4.run(ping_mod62)
            g1.run(ping_mod6_bad, expect="fail")
            g3.run(ping_mod6_bad2, expect="fail")

            server_proc = g1.run(netperf_srv6, bg=True)
            ctl.wait(2)
            g3.run(netperf_cli_tcp6, timeout=70)
            g3.run(netperf_cli_udp6, timeout=70)
            server_proc.intr()
        else:
            # IPv4
            g1.run(ping_mod)
            g4.run(ping_mod2)
            g1.run(ping_mod_bad, expect="fail")
            g3.run(ping_mod_bad2, expect="fail")

            server_proc = g1.run(netperf_srv, bg=True)
            ctl.wait(2)
            g3.run(netperf_cli_tcp, timeout=70)
            g3.run(netperf_cli_udp, timeout=70)
            server_proc.intr()
            # IPv6
            g1.run(ping_mod6)
            g4.run(ping_mod62)
            g1.run(ping_mod6_bad, expect="fail")
            g3.run(ping_mod6_bad2, expect="fail")

            server_proc = g1.run(netperf_srv6, bg=True)
            ctl.wait(2)
            g3.run(netperf_cli_tcp6, timeout=70)
            g3.run(netperf_cli_udp6, timeout=70)
            server_proc.intr()
