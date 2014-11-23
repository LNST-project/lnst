from lnst.Controller.Task import ctl

# ------
# SETUP
# ------

m1 = ctl.get_host("testmachine1")
m2 = ctl.get_host("testmachine2")

m1.sync_resources(modules=["IcmpPing", "Netperf"])
m2.sync_resources(modules=["IcmpPing", "Netperf"])

m1_ip = m1.get_ip("test_if")
m2_ip = m2.get_ip("test_if")

# ------
# TESTS
# ------

offloads = ["tso", "gro", "gso"]

ping_mod = ctl.get_module("IcmpPing",
                           options={
                               "addr" : m2_ip,
                               "count" : 100,
                               "iface" : m1.get_devname("test_if"),
                               "interval" : 0.1
                           })

netperf_srv = ctl.get_module("Netperf",
                              options = {
                                  "role" : "server",
                                  "bind" : m1_ip
                              })

netperf_cli_tcp = ctl.get_module("Netperf",
                                  options = {
                                      "role" : "client",
                                      "netperf_server" : m1_ip,
                                      "duration" : 60,
                                      "testname" : "TCP_STREAM",
                                      "netperf_opts" : "-L %s" % m2_ip
                                })

netperf_cli_udp = ctl.get_module("Netperf",
                                  options = {
                                      "role" : "client",
                                      "netperf_server" : m1_ip,
                                      "duration" : 60,
                                      "testname" : "UDP_STREAM",
                                      "netperf_opts" : "-L %s" % m2_ip
                                  })
for offload in offloads:
    for state in ["on", "off"]:
        m1.run("ethtool -K %s %s %s" % (m1.get_devname("test_if"), offload,
                                        state))
        m2.run("ethtool -K %s %s %s" % (m2.get_devname("test_if"), offload,
                                        state))
        m1.run(ping_mod)
        server_proc = m1.run(netperf_srv, bg=True)
        ctl.wait(2)
        m2.run(netperf_cli_tcp, timeout=65)
        m2.run(netperf_cli_udp, timeout=65)
        server_proc.intr()

ping_mod = ctl.get_module("IcmpPing",
                           options={
                               "addr" : m1_ip,
                               "count" : 100,
                               "iface" : m2.get_devname("test_if"),
                               "interval" : 0.1
                           })


netperf_srv = ctl.get_module("Netperf",
                              options = {
                                  "role" : "server",
                                  "bind" : m2_ip
                              })

netperf_cli_tcp = ctl.get_module("Netperf",
                                  options = {
                                      "role" : "client",
                                      "netperf_server" : m2_ip,
                                      "duration" : 60,
                                      "testname" : "TCP_STREAM",
                                      "netperf_opts" : "-L %s" % m1_ip
                                  })

netperf_cli_udp = ctl.get_module("Netperf",
                                  options = {
                                      "role" : "client",
                                      "netperf_server" : m2_ip,
                                      "duration" : 60,
                                      "testname" : "UDP_STREAM",
                                      "netperf_opts" : "-L %s" % m1_ip
                                  })

for offload in offloads:
    for state in ["on", "off"]:
        m1.run("ethtool -K %s %s %s" % (m1.get_devname("test_if"), offload,
                                        state))
        m2.run("ethtool -K %s %s %s" % (m2.get_devname("test_if"), offload,
                                        state))
        m2.run(ping_mod)
        server_proc = m2.run(netperf_srv, bg=True)
        ctl.wait(2)
        m1.run(netperf_cli_tcp, timeout=65)
        m1.run(netperf_cli_udp, timeout=65)
        server_proc.intr()
