import logging
from lnst.Controller.Task import ctl
from lnst.Controller.PerfRepoUtils import netperf_baseline_template
from lnst.Controller.PerfRepoUtils import netperf_result_template

# ------
# SETUP
# ------

mapping_file = ctl.get_alias("mapping_file")
perf_api = ctl.connect_PerfRepo(mapping_file)

product_name = ctl.get_alias("product_name")

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

offloads = ["gro", "gso", "tso", "rx", "tx"]
offload_settings = [ [("gro", "on"), ("gso", "on"), ("tso", "on"), ("tx", "on"), ("rx", "on")],
                     [("gro", "off"), ("gso", "on"), ("tso", "on"), ("tx", "on"), ("rx", "on")],
                     [("gro", "on"), ("gso", "off"),  ("tso", "off"), ("tx", "on"), ("rx", "on")],
                     [("gro", "on"), ("gso", "on"), ("tso", "off"), ("tx", "off"), ("rx", "on")],
                     [("gro", "on"), ("gso", "on"), ("tso", "on"), ("tx", "on"), ("rx", "off")]]

ipv = ctl.get_alias("ipv")
netperf_duration = int(ctl.get_alias("netperf_duration"))
nperf_reserve = int(ctl.get_alias("nperf_reserve"))
nperf_confidence = ctl.get_alias("nperf_confidence")
nperf_max_runs = int(ctl.get_alias("nperf_max_runs"))

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
                                      "duration" : netperf_duration,
                                      "testname" : "TCP_STREAM",
                                      "confidence" : nperf_confidence,
                                      "netperf_opts" : "-i %s -L %s" %
                                                          (nperf_max_runs, g3.get_ip("guestnic"))
                                  })

netperf_cli_udp = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" : g1.get_ip("guestnic"),
                                      "duration" : netperf_duration,
                                      "testname" : "UDP_STREAM",
                                      "confidence" : nperf_confidence,
                                      "netperf_opts" : "-i %s -L %s" %
                                                          (nperf_max_runs, g3.get_ip("guestnic"))
                                  })

netperf_cli_tcp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" :
                                          g1.get_ip("guestnic", 1),
                                      "duration" : netperf_duration,
                                      "testname" : "TCP_STREAM",
                                      "confidence" : nperf_confidence,
                                      "netperf_opts" :
                                          "-i %s -L %s -6" % (nperf_max_runs, g3.get_ip("guestnic", 1))
                                  })

netperf_cli_udp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" :
                                          g1.get_ip("guestnic", 1),
                                      "duration" : netperf_duration,
                                      "testname" : "UDP_STREAM",
                                      "confidence" : nperf_confidence,
                                      "netperf_opts" :
                                          "-i %s -L %s -6" % (nperf_max_runs, g3.get_ip("guestnic", 1))
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

for setting in offload_settings:
    for offload in setting:
        h1.run("ethtool -K %s %s %s" % (h1.get_devname("nic1"),
                                        offload[0], offload[1]))
        h1.run("ethtool -K %s %s %s" % (h1.get_devname("nic2"),
                                        offload[0], offload[1]))
        h2.run("ethtool -K %s %s %s" % (h2.get_devname("nic1"),
                                        offload[0], offload[1]))
        h2.run("ethtool -K %s %s %s" % (h2.get_devname("nic2"),
                                        offload[0], offload[1]))
        g1.run("ethtool -K %s %s %s" % (g1.get_devname("guestnic"),
                                        offload[0], offload[1]))
        g2.run("ethtool -K %s %s %s" % (g2.get_devname("guestnic"),
                                        offload[0], offload[1]))
        g3.run("ethtool -K %s %s %s" % (g3.get_devname("guestnic"),
                                        offload[0], offload[1]))
        g4.run("ethtool -K %s %s %s" % (g4.get_devname("guestnic"),
                                        offload[0], offload[1]))

    if ipv in [ 'ipv4', 'both' ]:
        g1.run(ping_mod)
        g4.run(ping_mod2)
        g1.run(ping_mod_bad, expect="fail")
        g3.run(ping_mod_bad2, expect="fail")

        server_proc = g1.run(netperf_srv, bg=True)
        ctl.wait(2)

        # prepare PerfRepo result for tcp
        result_tcp = perf_api.new_result("tcp_ipv4_id",
                                         "tcp_ipv4_result",
                                         hash_ignore=[
                                             'kernel_release',
                                             'redhat_release'])
        for offload in setting:
            result_tcp.set_parameter(offload[0], offload[1])
        result_tcp.add_tag(product_name)

        baseline = perf_api.get_baseline_of_result(result_tcp)
        netperf_baseline_template(netperf_cli_tcp, baseline)

        tcp_res_data = g3.run(netperf_cli_tcp,
                              timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

        netperf_result_template(result_tcp, tcp_res_data)
        perf_api.save_result(result_tcp)

        # prepare PerfRepo result for udp
        result_udp = perf_api.new_result("udp_ipv4_id",
                                         "udp_ipv4_result",
                                         hash_ignore=[
                                             'kernel_release',
                                             'redhat_release'])
        for offload in setting:
            result_udp.set_parameter(offload[0], offload[1])
        result_udp.add_tag(product_name)

        baseline = perf_api.get_baseline_of_result(result_udp)
        netperf_baseline_template(netperf_cli_udp, baseline)

        udp_res_data = g3.run(netperf_cli_udp,
                              timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

        netperf_result_template(result_udp, udp_res_data)
        perf_api.save_result(result_udp)

        server_proc.intr()
    if ipv in [ 'ipv6', 'both' ]:
        g1.run(ping_mod6)
        g4.run(ping_mod62)
        g1.run(ping_mod6_bad, expect="fail")
        g3.run(ping_mod6_bad2, expect="fail")

        server_proc = g1.run(netperf_srv6, bg=True)
        ctl.wait(2)

        # prepare PerfRepo result for tcp ipv6
        result_tcp = perf_api.new_result("tcp_ipv6_id",
                                         "tcp_ipv6_result",
                                         hash_ignore=[
                                             'kernel_release',
                                             'redhat_release'])
        for offload in setting:
            result_tcp.set_parameter(offload[0], offload[1])
        result_tcp.add_tag(product_name)

        baseline = perf_api.get_baseline_of_result(result_tcp)
        netperf_baseline_template(netperf_cli_tcp6, baseline)

        tcp_res_data = g3.run(netperf_cli_tcp6,
                              timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

        netperf_result_template(result_tcp, tcp_res_data)
        perf_api.save_result(result_tcp)

        # prepare PerfRepo result for udp ipv6
        result_udp = perf_api.new_result("udp_ipv6_id",
                                         "udp_ipv6_result",
                                         hash_ignore=[
                                             'kernel_release',
                                             'redhat_release'])
        for offload in setting:
            result_udp.set_parameter(offload[0], offload[1])
        result_udp.add_tag(product_name)

        baseline = perf_api.get_baseline_of_result(result_udp)
        netperf_baseline_template(netperf_cli_udp6, baseline)

        udp_res_data = g3.run(netperf_cli_udp6,
                              timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

        netperf_result_template(result_udp, udp_res_data)
        perf_api.save_result(result_udp)

        server_proc.intr()

#reset offload states
for offload in offloads:
    h1.run("ethtool -K %s %s %s" % (h1.get_devname("nic1"),
                                    offload, "on"))
    h1.run("ethtool -K %s %s %s" % (h1.get_devname("nic2"),
                                    offload, "on"))
    h2.run("ethtool -K %s %s %s" % (h2.get_devname("nic1"),
                                    offload, "on"))
    h2.run("ethtool -K %s %s %s" % (h2.get_devname("nic2"),
                                    offload, "on"))
    g1.run("ethtool -K %s %s %s" % (g1.get_devname("guestnic"),
                                    offload, "on"))
    g2.run("ethtool -K %s %s %s" % (g2.get_devname("guestnic"),
                                    offload, "on"))
    g3.run("ethtool -K %s %s %s" % (g3.get_devname("guestnic"),
                                    offload, "on"))
    g4.run("ethtool -K %s %s %s" % (g4.get_devname("guestnic"),
                                    offload, "on"))
