import logging
from lnst.Controller.Task import ctl
from lnst.Controller.PerfRepoUtils import parse_id_mapping, get_id

# ------
# SETUP
# ------

mapping_file = ctl.get_alias("mapping_file")
mapping = parse_id_mapping(mapping_file)

product_name = ctl.get_alias("product_name")

tcp_ipv4_id = get_id(mapping, "tcp_ipv4_id")
tcp_ipv6_id = get_id(mapping, "tcp_ipv6_id")
udp_ipv4_id = get_id(mapping, "udp_ipv4_id")
udp_ipv6_id = get_id(mapping, "udp_ipv6_id")

if tcp_ipv4_id is not None or\
   tcp_ipv6_id is not None or\
   udp_ipv4_id is not None or\
   udp_ipv6_id is not None:
    perf_api = ctl.connect_PerfRepo()
    logging.info("PerfRepo support enabled for this run.")
else:
    logging.info("PerfRepo support disabled for this run.")

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
        if ipv in [ 'ipv4', 'both' ]:
            g1.run(ping_mod)
            g4.run(ping_mod2)
            g1.run(ping_mod_bad, expect="fail")
            g3.run(ping_mod_bad2, expect="fail")

            # prepare PerfRepo result for tcp
            result_tcp = None
            result_udp = None
            if tcp_ipv4_id is not None:
                result_tcp = perf_api.new_result(tcp_ipv4_id, "tcp_ipv4_result")
                result_tcp.set_parameter(offload, state)
                if product_name is not None:
                    result_tcp.set_tag(product_name)
                res_hash = result_tcp.generate_hash(['kernel_release',
                                                     'redhat_release'])
                result_tcp.set_tag(res_hash)

                baseline = None
                report_id = get_id(mapping, res_hash)
                if report_id is not None:
                    baseline = perf_api.get_baseline(report_id)

                if baseline is not None:
                    baseline_throughput = baseline.get_value('throughput').get_result()
                    baseline_deviation = baseline.get_value('throughput_deviation').get_result()
                    netperf_cli_tcp.update_options({'threshold': '%s bits/sec' % baseline_throughput,
                                                    'threshold_deviation': '%s bits/sec' % baseline_deviation})
            # prepare PerfRepo result for udp
            if udp_ipv4_id is not None:
                result_udp = perf_api.new_result(udp_ipv4_id, "udp_ipv4_result")
                result_udp.set_parameter(offload, state)
                if product_name is not None:
                    result_udp.set_tag(product_name)
                res_hash = result_udp.generate_hash(['kernel_release',
                                                     'redhat_release'])
                result_udp.set_tag(res_hash)

                baseline = None
                report_id = get_id(mapping, res_hash)
                if report_id is not None:
                    baseline = perf_api.get_baseline(report_id)

                if baseline is not None:
                    baseline_throughput = baseline.get_value('throughput').get_result()
                    baseline_deviation = baseline.get_value('throughput_deviation').get_result()
                    netperf_cli_udp.update_options({'threshold': '%s bits/sec' % baseline_throughput,
                                                    'threshold_deviation': '%s bits/sec' % baseline_deviation})

            server_proc = g1.run(netperf_srv, bg=True)
            ctl.wait(2)
            tcp_res_data = g3.run(netperf_cli_tcp,
                                  timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)
            udp_res_data = g3.run(netperf_cli_udp,
                                  timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)
            server_proc.intr()

            if result_tcp is not None and\
               tcp_res_data.get_result() is not None and\
               tcp_res_data.get_result()['res_data'] is not None:
                rate = tcp_res_data.get_result()['res_data']['rate']
                deviation = tcp_res_data.get_result()['res_data']['rate_deviation']

                result_tcp.add_value('throughput', rate)
                result_tcp.add_value('throughput_min', rate - deviation)
                result_tcp.add_value('throughput_max', rate + deviation)
                result_tcp.add_value('throughput_deviation', deviation)
                perf_api.save_result(result_tcp)

            if result_udp is not None and udp_res_data.get_result() is not None and\
               udp_res_data.get_result()['res_data'] is not None:
                rate = udp_res_data.get_result()['res_data']['rate']
                deviation = udp_res_data.get_result()['res_data']['rate_deviation']

                result_udp.add_value('throughput', rate)
                result_udp.add_value('throughput_min', rate - deviation)
                result_udp.add_value('throughput_max', rate + deviation)
                result_udp.add_value('throughput_deviation', deviation)
                perf_api.save_result(result_udp)

        if ipv in [ 'ipv6', 'both' ]:
            g1.run(ping_mod6)
            g4.run(ping_mod62)
            g1.run(ping_mod6_bad, expect="fail")
            g3.run(ping_mod6_bad2, expect="fail")

            # prepare PerfRepo result for tcp ipv6
            result_tcp = None
            result_udp = None
            if tcp_ipv6_id is not None:
                result_tcp = perf_api.new_result(tcp_ipv6_id, "tcp_ipv6_result")
                result_tcp.set_parameter(offload, state)
                if product_name is not None:
                    result_tcp.set_tag(product_name)
                res_hash = result_tcp.generate_hash(['kernel_release',
                                                     'redhat_release'])
                result_tcp.set_tag(res_hash)

                baseline = None
                report_id = get_id(mapping, res_hash)
                if report_id is not None:
                    baseline = perf_api.get_baseline(report_id)

                if baseline is not None:
                    baseline_throughput = baseline.get_value('throughput').get_result()
                    baseline_deviation = baseline.get_value('throughput_deviation').get_result()
                    netperf_cli_tcp.update_options({'threshold': '%s bits/sec' % baseline_throughput,
                                                    'threshold_deviation': '%s bits/sec' % baseline_deviation})

            # prepare PerfRepo result for udp ipv6
            if udp_ipv6_id is not None:
                result_udp = perf_api.new_result(udp_ipv6_id, "udp_ipv6_result")
                result_udp.set_parameter(offload, state)
                if product_name is not None:
                    result_udp.set_tag(product_name)
                res_hash = result_udp.generate_hash(['kernel_release',
                                                     'redhat_release'])
                result_udp.set_tag(res_hash)

                baseline = None
                report_id = get_id(mapping, res_hash)
                if report_id is not None:
                    baseline = perf_api.get_baseline(report_id)

                if baseline is not None:
                    baseline_throughput = baseline.get_value('throughput').get_result()
                    baseline_deviation = baseline.get_value('throughput_deviation').get_result()
                    netperf_cli_udp.update_options({'threshold': '%s bits/sec' % baseline_throughput,
                                                    'threshold_deviation': '%s bits/sec' % baseline_deviation})

            server_proc = g1.run(netperf_srv6, bg=True)
            ctl.wait(2)
            tcp_res_data = g3.run(netperf_cli_tcp6,
                                  timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)
            udp_res_data = g3.run(netperf_cli_udp6,
                                  timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)
            server_proc.intr()

            if result_tcp is not None and tcp_res_data.get_result() is not None and\
               tcp_res_data.get_result()['res_data'] is not None:
                rate = tcp_res_data.get_result()['res_data']['rate']
                deviation = tcp_res_data.get_result()['res_data']['rate_deviation']

                result_tcp.add_value('throughput', rate)
                result_tcp.add_value('throughput_min', rate - deviation)
                result_tcp.add_value('throughput_max', rate + deviation)
                result_tcp.add_value('throughput_deviation', deviation)
                perf_api.save_result(result_tcp)

            if result_udp is not None and udp_res_data.get_result() is not None and\
               udp_res_data.get_result()['res_data'] is not None:
                rate = udp_res_data.get_result()['res_data']['rate']
                deviation = udp_res_data.get_result()['res_data']['rate_deviation']

                result_udp.add_value('throughput', rate)
                result_udp.add_value('throughput_min', rate - deviation)
                result_udp.add_value('throughput_max', rate + deviation)
                result_udp.add_value('throughput_deviation', deviation)
                perf_api.save_result(result_udp)
