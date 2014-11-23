from lnst.Controller.Task import ctl

# ------
# SETUP
# ------

# Host 1 + guests 1 and 2
#h1 = ctl.get_host("host1")
g1 = ctl.get_host("guest1")
g1.sync_resources(modules=["IcmpPing", "Netperf"])
g2 = ctl.get_host("guest2")
g2.sync_resources(modules=["IcmpPing", "Netperf"])

# Host 2 + guests 3 and 4
#h2 = ctl.get_host("host2")
g3 = ctl.get_host("guest3")
g3.sync_resources(modules=["IcmpPing", "Netperf"])
g4 = ctl.get_host("guest4")
g4.sync_resources(modules=["IcmpPing", "Netperf"])

# ------
# TESTS
# ------

offloads = ["gso", "gro", "tso"]

ping_mod = ctl.get_module("IcmpPing",
                           options={
                               "addr" : g3.get_ip("guestnic"),
                               "count" : 100,
                               "iface" : g1.get_devname("guestnic"),
                               "interval" : 0.1
                           })
ping_mod2 = ctl.get_module("IcmpPing",
                           options={
                               "addr" : g2.get_ip("guestnic"),
                               "count" : 100,
                               "iface" : g4.get_devname("guestnic"),
                               "interval" : 0.1
                           })
netperf_srv = ctl.get_module("Netperf",
                              options={
                                  "role": "server",
                                  "bind" : g1.get_ip("guestnic")
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

for offload in offloads:
    for state in ["on", "off"]:
        g1.run("ethtool -K %s %s %s" % (g1.get_devname("guestnic"),
                                        offload, state))
        g2.run("ethtool -K %s %s %s" % (g2.get_devname("guestnic"),
                                        offload, state))
        g3.run("ethtool -K %s %s %s" % (g3.get_devname("guestnic"),
                                        offload, state))
        g4.run("ethtool -K %s %s %s" % (g4.get_devname("guestnic"),
                                        offload, state))
        g1.run(ping_mod)
        g4.run(ping_mod2)
        g1.run(ping_mod_bad, expect="fail")
        g3.run(ping_mod_bad2, expect="fail")

        g1.run(netperf_srv, bg=True, timeout=125)
        ctl.wait(2)
        g3.run(netperf_cli_tcp, timeout=65)
        g3.run(netperf_cli_udp, timeout=65)
