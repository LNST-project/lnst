from lnst.Controller.Task import ctl

# ------
# SETUP
# ------

h1 = ctl.get_host("host1")
g1 = ctl.get_host("guest1")

h2 = ctl.get_host("host2")

g1.sync_resources(modules=["IcmpPing", "Netperf"])
h2.sync_resources(modules=["IcmpPing", "Netperf"])

# ------
# TESTS
# ------

offloads = ["gso", "gro", "tso"]

ping_mod = ctl.get_module("IcmpPing",
                           options={
                               "addr" : h2.get_ip("vlan10"),
                               "count" : 100,
                               "iface" : g1.get_devname("guestnic"),
                               "interval" : 0.1
                           })
netperf_srv = ctl.get_module("Netperf",
                              options={
                                  "role" : "server",
                                  "bind" : g1.get_ip("guestnic")
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

for offload in offloads:
    for state in ["on", "off"]:
            g1.run("ethtool -K %s %s %s" % (g1.get_devname("guestnic"),
                                            offload, state))
            h2.run("ethtool -K %s %s %s" % (h2.get_devname("nic"),
                                            offload, state))
            g1.run(ping_mod)
            server_proc = g1.run(netperf_srv, bg=True)
            ctl.wait(2)
            h2.run(netperf_cli_tcp, timeout=65)
            h2.run(netperf_cli_udp, timeout=65)

            server_proc.intr()
