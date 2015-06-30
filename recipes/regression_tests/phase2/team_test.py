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

offloads = ["tso", "gro", "gso"]

ipv = ctl.get_alias("ipv")
mtu = ctl.get_alias("mtu")
netperf_duration = ctl.get_alias("netperf_duration")

test_if1 = m1.get_interface("test_if")
test_if1.set_mtu(mtu)
test_if2 = m2.get_interface("test_if")
test_if2.set_mtu(mtu)


ping_mod = ctl.get_module("IcmpPing",
                           options={
                               "addr" : m2.get_ip("test_if", 0),
                               "count" : 100,
                               "iface" : m1.get_devname("test_if"),
                               "interval" : 0.1
                           })

ping_mod6 = ctl.get_module("Icmp6Ping",
                           options={
                               "addr" : m2.get_ip("test_if", 1),
                               "count" : 100,
                               "iface" : m1.get_ip("test_if", 1),
                               "interval" : 0.1
                           })

netperf_srv = ctl.get_module("Netperf",
                              options = {
                                  "role" : "server",
                                  "bind" : m1.get_ip("test_if", 0)
                              })

netperf_srv6 = ctl.get_module("Netperf",
                              options = {
                                  "role" : "server",
                                  "bind" : m1.get_ip("test_if", 1),
                                  "netperf_opts" : " -6"
                              })

netperf_cli_tcp = ctl.get_module("Netperf",
                                  options = {
                                      "role" : "client",
                                      "netperf_server" : m1.get_ip("test_if", 0),
                                      "duration" : netperf_duration,
                                      "testname" : "TCP_STREAM",
                                      "netperf_opts" : "-L %s" % m2.get_ip("test_if", 0)
                                })

netperf_cli_udp = ctl.get_module("Netperf",
                                  options = {
                                      "role" : "client",
                                      "netperf_server" : m1.get_ip("test_if", 0),
                                      "duration" : netperf_duration,
                                      "testname" : "UDP_STREAM",
                                      "netperf_opts" : "-L %s" % m2.get_ip("test_if", 0)
                                  })

netperf_cli_tcp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" :
                                          m1.get_ip("test_if", 1),
                                      "duration" : netperf_duration,
                                      "testname" : "TCP_STREAM",
                                      "netperf_opts" :
                                          "-L %s -6" % m2.get_ip("test_if", 1)
                                  })
netperf_cli_udp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" :
                                          m1.get_ip("test_if", 1),
                                      "duration" : netperf_duration,
                                      "testname" : "UDP_STREAM",
                                      "netperf_opts" :
                                          "-L %s -6" % m2.get_ip("test_if", 1)
                                  })

ctl.wait(15)

for offload in offloads:
    for state in ["off", "on"]:
        m1.run("ethtool -K %s %s %s" % (m1.get_devname("test_if"), offload,
                                        state))
        m2.run("ethtool -K %s %s %s" % (m2.get_devname("test_if"), offload,
                                        state))
        if ipv in [ 'ipv4', 'both' ]:
            m1.run(ping_mod)
            server_proc = m1.run(netperf_srv, bg=True)
            ctl.wait(2)
            m2.run(netperf_cli_tcp, timeout=70)
            m2.run(netperf_cli_udp, timeout=70)
            server_proc.intr()

        if ipv in [ 'ipv6', 'both' ]:
            m1.run(ping_mod6)
            server_proc = m1.run(netperf_srv6, bg=True)
            ctl.wait(2)
            m2.run(netperf_cli_tcp6, timeout=70)
            m2.run(netperf_cli_udp6, timeout=70)
            server_proc.intr()

ping_mod = ctl.get_module("IcmpPing",
                           options={
                               "addr" : m1.get_ip("test_if", 0),
                               "count" : 100,
                               "iface" : m2.get_devname("test_if"),
                               "interval" : 0.1
                           })

ping_mod6 = ctl.get_module("Icmp6Ping",
                           options={
                               "addr" : m1.get_ip("test_if", 1),
                               "count" : 100,
                               "iface" : m2.get_devname("test_if"),
                               "interval" : 0.1
                           })

netperf_srv = ctl.get_module("Netperf",
                              options = {
                                  "role" : "server",
                                  "bind" : m2.get_ip("test_if", 0)
                              })

netperf_srv6 = ctl.get_module("Netperf",
                              options = {
                                  "role" : "server",
                                  "bind" : m2.get_ip("test_if", 1),
                                  "netperf_opts" : " -6"
                              })

netperf_cli_tcp = ctl.get_module("Netperf",
                                  options = {
                                      "role" : "client",
                                      "netperf_server" : m2.get_ip("test_if", 0),
                                      "duration" : netperf_duration,
                                      "testname" : "TCP_STREAM",
                                      "netperf_opts" : "-L %s" % m1.get_ip("test_if", 0)
                                  })

netperf_cli_udp = ctl.get_module("Netperf",
                                  options = {
                                      "role" : "client",
                                      "netperf_server" : m2.get_ip("test_if", 0),
                                      "duration" : netperf_duration,
                                      "testname" : "UDP_STREAM",
                                      "netperf_opts" : "-L %s" % m1.get_ip("test_if", 0)
                                  })

netperf_cli_tcp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" :
                                          m2.get_ip("test_if", 1),
                                      "duration" : netperf_duration,
                                      "testname" : "TCP_STREAM",
                                      "netperf_opts" :
                                          "-L %s -6" % m1.get_ip("test_if", 1)
                                  })
netperf_cli_udp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" :
                                          m2.get_ip("test_if", 1),
                                      "duration" : netperf_duration,
                                      "testname" : "UDP_STREAM",
                                      "netperf_opts" :
                                          "-L %s -6" % m1.get_ip("test_if", 1)
                                  })

for offload in offloads:
    for state in ["off", "on"]:
        m1.run("ethtool -K %s %s %s" % (m1.get_devname("test_if"), offload,
                                        state))
        m2.run("ethtool -K %s %s %s" % (m2.get_devname("test_if"), offload,
                                        state))
        if ipv in [ 'ipv4', 'both' ]:
            m2.run(ping_mod)
            server_proc = m2.run(netperf_srv, bg=True)
            ctl.wait(2)
            m1.run(netperf_cli_tcp, timeout=70)
            m1.run(netperf_cli_udp, timeout=70)
            server_proc.intr()

        if ipv in [ 'ipv6', 'both' ]:
            m2.run(ping_mod6)
            server_proc = m2.run(netperf_srv6, bg=True)
            ctl.wait(2)
            m1.run(netperf_cli_tcp6, timeout=70)
            m1.run(netperf_cli_udp6, timeout=70)
            server_proc.intr()
