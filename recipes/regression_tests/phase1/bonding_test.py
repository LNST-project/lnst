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
                               "iface" : m1.get_devname("test_if"),
                               "interval" : 0.1
                           })

netperf_srv = ctl.get_module("Netperf",
                              options = {
                                  "role" : "server",
                                  "bind" : m1.get_ip("test_if", 0)
                              })

netperf_srv6 = ctl.get_module("Netperf",
                              options={
                                  "role" : "server",
                                  "bind" : m1.get_ip("test_if", 1),
                                  "netperf_opts" : " -6",
                              })

netperf_cli_tcp = ctl.get_module("Netperf",
                                  options = {
                                      "role" : "client",
                                      "netperf_server" : m1.get_ip("test_if", 0),
                                      "duration" : netperf_duration,
                                      "testname" : "TCP_STREAM",
                                      "confidence" : "99,5",
                                      "netperf_opts" : "-i 5 -L %s" % m2.get_ip("test_if", 0)
                                })

netperf_cli_udp = ctl.get_module("Netperf",
                                  options = {
                                      "role" : "client",
                                      "netperf_server" : m1.get_ip("test_if", 0),
                                      "duration" : netperf_duration,
                                      "testname" : "UDP_STREAM",
                                      "confidence" : "99,5",
                                      "netperf_opts" : "-i 5 -L %s" % m2.get_ip("test_if", 0)
                                  })

netperf_cli_tcp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" :
                                          m1.get_ip("test_if", 1),
                                      "duration" : netperf_duration,
                                      "testname" : "TCP_STREAM",
                                      "confidence" : "99,5",
                                      "netperf_opts" :
                                          "-i 5 -L %s -6" % m2.get_ip("test_if", 1)
                                  })
netperf_cli_udp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" :
                                          m1.get_ip("test_if", 1),
                                      "duration" : netperf_duration,
                                      "testname" : "UDP_STREAM",
                                      "confidence" : "99,5",
                                      "netperf_opts" :
                                          "-i 5 -L %s -6" % m2.get_ip("test_if", 1)
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

            server_proc = m1.run(netperf_srv, bg=True)
            ctl.wait(2)
            tcp_res_data = m2.run(netperf_cli_tcp, timeout = int(netperf_duration)*5 + 20)
            udp_res_data = m2.run(netperf_cli_udp, timeout = int(netperf_duration)*5 + 20)
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
            m1.run(ping_mod6)

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

            server_proc = m1.run(netperf_srv6, bg=True)
            ctl.wait(2)
            tcp_res_data = m2.run(netperf_cli_tcp6, timeout = int(netperf_duration)*5 + 20)
            udp_res_data = m2.run(netperf_cli_udp6, timeout = int(netperf_duration)*5 + 20)
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
