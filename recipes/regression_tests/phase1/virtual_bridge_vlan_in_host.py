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

mtu = ctl.get_alias("mtu")
enable_udp_perf = ctl.get_alias("enable_udp_perf")

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
                                      "duration" : netperf_duration,
                                      "testname" : "TCP_STREAM",
                                      "confidence" : nperf_confidence,
                                      "netperf_opts" : "-i %s -L %s" %
                                                            (nperf_max_runs, h2.get_ip("vlan10"))
                                  })

netperf_cli_udp = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" : g1.get_ip("guestnic"),
                                      "duration" : netperf_duration,
                                      "testname" : "UDP_STREAM",
                                      "confidence" : nperf_confidence,
                                      "netperf_opts" : "-i %s -L %s" %
                                                            (nperf_max_runs, h2.get_ip("vlan10"))
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
                                          "-i %s -L %s -6" % (nperf_max_runs, h2.get_ip("vlan10", 1))
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
                                          "-i %s -L %s -6" % (nperf_max_runs, h2.get_ip("vlan10", 1))
                                  })

# configure mtu
h1.get_interface("nic").set_mtu(mtu)
h1.get_interface("tap").set_mtu(mtu)
h1.get_interface("vlan10").set_mtu(mtu)
h1.get_interface("br").set_mtu(mtu)

g1.get_interface("guestnic").set_mtu(mtu)

h2.get_interface("nic").set_mtu(mtu)
h2.get_interface("vlan10").set_mtu(mtu)

ctl.wait(15)

for setting in offload_settings:
    for offload in setting:
        g1.run("ethtool -K %s %s %s" % (g1.get_devname("guestnic"),
                                        offload[0], offload[1]))
        h1.run("ethtool -K %s %s %s" % (h1.get_devname("nic"),
                                        offload[0], offload[1]))
        h2.run("ethtool -K %s %s %s" % (h2.get_devname("nic"),
                                        offload[0], offload[1]))

    if ipv in [ 'ipv4', 'both' ]:
        g1.run(ping_mod)

        server_proc = g1.run(netperf_srv, bg=True)
        ctl.wait(2)

        # prepare PerfRepo result for tcp
        result_tcp = perf_api.new_result("tcp_ipv4_id",
                                         "tcp_ipv4_result",
                                         hash_ignore=['kernel_release',
                                             'redhat_release',
                                             r'guest\d+\.hostname',
                                             r'guest\d+\..*hwaddr'])
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
        if enable_udp_perf is not None:
            result_udp = perf_api.new_result("udp_ipv4_id",
                                             "udp_ipv4_result",
                                             hash_ignore=['kernel_release',
                                                 'redhat_release',
                                                 r'guest\d+\.hostname',
                                                 r'guest\d+\..*hwaddr'])
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
                                         hash_ignore=['kernel_release',
                                             'redhat_release',
                                             r'guest\d+\.hostname',
                                             r'guest\d+\..*hwaddr'])
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
        if enable_udp_perf:
            result_udp = perf_api.new_result("udp_ipv6_id",
                                             "udp_ipv6_result",
                                             hash_ignore=['kernel_release',
                                                 'redhat_release',
                                                 r'guest\d+\.hostname',
                                                 r'guest\d+\..*hwaddr'])
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
for offload in offloads:
    g1.run("ethtool -K %s %s %s" % (g1.get_devname("guestnic"),
                                    offload, "on"))
    h1.run("ethtool -K %s %s %s" % (h1.get_devname("nic"),
                                    offload, "on"))
    h2.run("ethtool -K %s %s %s" % (h2.get_devname("nic"),
                                    offload, "on"))
