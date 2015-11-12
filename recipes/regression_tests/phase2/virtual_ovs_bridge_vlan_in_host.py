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

h1 = ctl.get_host("host1")
g1 = ctl.get_host("guest1")

h2 = ctl.get_host("host2")

g1.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Netperf"])
h2.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Netperf"])

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
nperf_cpupin = ctl.get_alias("nperf_cpupin")
nperf_cpu_util = ctl.get_alias("nperf_cpu_util")

h2_vlan10 = h2.get_interface("vlan10")
g1_guestnic = g1.get_interface("guestnic")
h1_nic = h1.get_interface("nic")
h2_nic = h2.get_interface("nic")

ping_mod = ctl.get_module("IcmpPing",
                           options={
                               "addr" : h2_vlan10.get_ip(0),
                               "count" : 100,
                               "iface" : g1_guestnic.get_devname(),
                               "interval" : 0.1
                           })

ping_mod6 = ctl.get_module("Icmp6Ping",
                           options={
                               "addr" : h2_vlan10.get_ip(1),
                               "count" : 100,
                               "iface" : g1_guestnic.get_ip(1),
                               "interval" : 0.1
                           })

netperf_srv = ctl.get_module("Netperf",
                              options={
                                  "role" : "server",
                                  "bind" : g1_guestnic.get_ip(0)
                              })

netperf_srv6 = ctl.get_module("Netperf",
                              options={
                                  "role" : "server",
                                  "bind" : g1_guestnic.get_ip(1),
                                  "netperf_opts" : " -6",
                              })

p_opts = "-i %s -L %s" % (nperf_max_runs, h2_vlan10.get_ip(0))
if nperf_cpupin:
    p_opts += " -T%s" % nperf_cpupin

netperf_cli_tcp = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" : g1_guestnic.get_ip(0),
                                      "duration" : netperf_duration,
                                      "testname" : "TCP_STREAM",
                                      "confidence" : nperf_confidence,
                                      "cpu_util" : nperf_cpu_util,
                                      "netperf_opts" : p_opts
                                  })

netperf_cli_udp = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" : g1_guestnic.get_ip(0),
                                      "duration" : netperf_duration,
                                      "testname" : "UDP_STREAM",
                                      "confidence" : nperf_confidence,
                                      "cpu_util" : nperf_cpu_util,
                                      "netperf_opts" : p_opts
                                  })

netperf_cli_tcp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" :
                                          g1_guestnic.get_ip(1),
                                      "duration" : netperf_duration,
                                      "testname" : "TCP_STREAM",
                                      "confidence" : nperf_confidence,
                                      "cpu_util" : nperf_cpu_util,
                                      "netperf_opts" :
                                          "-i %s -L %s -6" % (nperf_max_runs, h2_vlan10.get_ip(1))
                                  })

netperf_cli_udp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" :
                                          g1_guestnic.get_ip(1),
                                      "duration" : netperf_duration,
                                      "testname" : "UDP_STREAM",
                                      "confidence" : nperf_confidence,
                                      "cpu_util" : nperf_cpu_util,
                                      "netperf_opts" :
                                          "-i %s -L %s -6" % (nperf_max_runs, h2_vlan10.get_ip(1))
                                  })
ctl.wait(15)

for setting in offload_settings:
    dev_features = ""
    for offload in setting:
        dev_features += " %s %s" % (offload[0], offload[1])
    h1.run("ethtool -K %s %s" % (h1_nic.get_devname(), dev_features))
    g1.run("ethtool -K %s %s" % (g1_guestnic.get_devname(), dev_features))
    h2.run("ethtool -K %s %s" % (h2_nic.get_devname(), dev_features))

    if ipv in [ 'ipv4', 'both' ]:
        g1.run(ping_mod)

        server_proc = g1.run(netperf_srv, bg=True)
        ctl.wait(2)

        # prepare PerfRepo result for tcp
        result_tcp = perf_api.new_result("tcp_ipv4_id",
                                         "tcp_ipv4_result",
                                         hash_ignore=[
                                             'kernel_release',
                                             'redhat_release',
                                             r'guest\d+\.hostname',
                                             r'guest\d+\..*hwaddr',
                                             r'host\d+\..*tap\d*\.hwaddr',
                                             r'host\d+\..*tap\d*\.devname'])
        for offload in setting:
            result_tcp.set_parameter(offload[0], offload[1])
        result_tcp.add_tag(product_name)

        baseline = perf_api.get_baseline_of_result(result_tcp)
        netperf_baseline_template(netperf_cli_tcp, baseline)

        tcp_res_data = h2.run(netperf_cli_tcp,
                              timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

        netperf_result_template(result_tcp, tcp_res_data)
        perf_api.save_result(result_tcp)

        # prepare PerfRepo result for udp
        result_udp = perf_api.new_result("udp_ipv4_id",
                                         "udp_ipv4_result",
                                         hash_ignore=[
                                             'kernel_release',
                                             'redhat_release',
                                             r'guest\d+\.hostname',
                                             r'guest\d+\..*hwaddr',
                                             r'host\d+\..*tap\d*\.hwaddr',
                                             r'host\d+\..*tap\d*\.devname'])
        for offload in setting:
            result_udp.set_parameter(offload[0], offload[1])
        result_udp.add_tag(product_name)

        baseline = perf_api.get_baseline_of_result(result_udp)
        netperf_baseline_template(netperf_cli_udp, baseline)

        udp_res_data = h2.run(netperf_cli_udp,
                              timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

        netperf_result_template(result_udp, udp_res_data)
        perf_api.save_result(result_udp)

        server_proc.intr()

    if ipv in [ 'ipv6', 'both' ]:
        g1.run(ping_mod6)

        server_proc = g1.run(netperf_srv6, bg=True)
        ctl.wait(2)

        # prepare PerfRepo result for tcp ipv6
        result_tcp = perf_api.new_result("tcp_ipv6_id",
                                         "tcp_ipv6_result",
                                         hash_ignore=[
                                             'kernel_release',
                                             'redhat_release',
                                             r'guest\d+\.hostname',
                                             r'guest\d+\..*hwaddr',
                                             r'host\d+\..*tap\d*\.hwaddr',
                                             r'host\d+\..*tap\d*\.devname'])
        for offload in setting:
            result_tcp.set_parameter(offload[0], offload[1])
        result_tcp.add_tag(product_name)

        baseline = perf_api.get_baseline_of_result(result_tcp)
        netperf_baseline_template(netperf_cli_tcp6, baseline)

        tcp_res_data = h2.run(netperf_cli_tcp6,
                              timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

        netperf_result_template(result_tcp, tcp_res_data)
        perf_api.save_result(result_tcp)

        # prepare PerfRepo result for udp ipv6
        result_udp = perf_api.new_result("udp_ipv6_id",
                                         "udp_ipv6_result",
                                         hash_ignore=[
                                             'kernel_release',
                                             'redhat_release',
                                             r'guest\d+\.hostname',
                                             r'guest\d+\..*hwaddr',
                                             r'host\d+\..*tap\d*\.hwaddr',
                                             r'host\d+\..*tap\d*\.devname'])
        for offload in setting:
            result_udp.set_parameter(offload[0], offload[1])
        result_udp.add_tag(product_name)

        baseline = perf_api.get_baseline_of_result(result_udp)
        netperf_baseline_template(netperf_cli_udp6, baseline)

        udp_res_data = h2.run(netperf_cli_udp6,
                              timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

        netperf_result_template(result_udp, udp_res_data)
        perf_api.save_result(result_udp)

        server_proc.intr()

#reset offload states
dev_features = ""
for offload in offloads:
    dev_features += " %s %s" % (offload, "on")
h1.run("ethtool -K %s %s" % (h1_nic.get_devname(), dev_features))
g1.run("ethtool -K %s %s" % (g1_guestnic.get_devname(), dev_features))
h2.run("ethtool -K %s %s" % (h2_nic.get_devname(), dev_features))
