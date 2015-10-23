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

m1 = ctl.get_host("testmachine1")
m2 = ctl.get_host("testmachine2")

m1.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Netperf"])
m2.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Netperf"])

# ------
# TESTS
# ------

vlans = ["vlan10", "vlan20", "vlan30"]
offloads = ["gro", "gso", "tso", "rx", "tx"]
offload_settings = [ [("gro", "on"), ("gso", "on"), ("tso", "on"), ("tx", "on"), ("rx", "on")],
                     [("gro", "off"), ("gso", "on"), ("tso", "on"), ("tx", "on"), ("rx", "on")],
                     [("gro", "on"), ("gso", "off"),  ("tso", "off"), ("tx", "on"), ("rx", "on")],
                     [("gro", "on"), ("gso", "on"), ("tso", "off"), ("tx", "off"), ("rx", "on")],
                     [("gro", "on"), ("gso", "on"), ("tso", "on"), ("tx", "on"), ("rx", "off")]]

ipv = ctl.get_alias("ipv")
mtu = ctl.get_alias("mtu")
netperf_duration = int(ctl.get_alias("netperf_duration"))
nperf_reserve = int(ctl.get_alias("nperf_reserve"))
nperf_confidence = ctl.get_alias("nperf_confidence")
nperf_max_runs = int(ctl.get_alias("nperf_max_runs"))

m1_phy1 = m1.get_interface("eth1")
m1_phy1.set_mtu(mtu)
m2_phy1 = m2.get_interface("eth1")
m2_phy1.set_mtu(mtu)

for vlan in vlans:
    vlan_if1 = m1.get_interface(vlan)
    vlan_if1.set_mtu(mtu)
    vlan_if2 = m2.get_interface(vlan)
    vlan_if2.set_mtu(mtu)

ctl.wait(15)

ping_mod = ctl.get_module("IcmpPing",
                           options={
                               "count" : 100,
                               "interval" : 0.1
                           })
ping_mod6 = ctl.get_module("Icmp6Ping",
                           options={
                               "count" : 100,
                               "interval" : 0.1
                           })
netperf_srv = ctl.get_module("Netperf",
                              options={
                                  "role" : "server"
                              })
netperf_srv6 = ctl.get_module("Netperf",
                              options={
                                  "role" : "server",
                                  "netperf_opts" : " -6"
                              })
netperf_cli_tcp = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "duration" : netperf_duration,
                                      "testname" : "TCP_STREAM",
                                      "confidence" : nperf_confidence
                                  })
netperf_cli_udp = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "duration" : netperf_duration,
                                      "testname" : "UDP_STREAM",
                                      "confidence" : nperf_confidence
                                  })
netperf_cli_tcp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "duration" : netperf_duration,
                                      "testname" : "TCP_STREAM",
                                      "confidence" : nperf_confidence
                                  })
netperf_cli_udp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "duration" : netperf_duration,
                                      "testname" : "UDP_STREAM",
                                      "confidence" : nperf_confidence
                                  })

for vlan1 in vlans:
    for vlan2 in vlans:
        ping_mod.update_options({"addr": m2.get_ip(vlan2, 0),
                                 "iface": m1.get_devname(vlan1)})

        ping_mod6.update_options({"addr": m2.get_ip(vlan2, 1),
                                  "iface": m1.get_ip(vlan1, 1)})

        netperf_srv.update_options({"bind": m1.get_ip(vlan1, 0)})

        netperf_srv6.update_options({"bind": m1.get_ip(vlan1, 1)})

        netperf_cli_tcp.update_options({"netperf_server": m1.get_ip(vlan1, 0),
                                        "netperf_opts": "-i %s -L %s" % (nperf_max_runs, m2.get_ip(vlan1, 0))})

        netperf_cli_udp.update_options({"netperf_server": m1.get_ip(vlan1, 0),
                                        "netperf_opts": "-i %s -L %s" % (nperf_max_runs, m2.get_ip(vlan1, 0))})

        netperf_cli_tcp6.update_options({"netperf_server": m1.get_ip(vlan1, 1),
                                         "netperf_opts": "-i %s -L %s -6" % (nperf_max_runs, m2.get_ip(vlan1, 1))})

        netperf_cli_udp6.update_options({"netperf_server": m1.get_ip(vlan1, 1),
                                         "netperf_opts": "-i %s -L %s -6" % (nperf_max_runs, m2.get_ip(vlan1, 1))})

        if vlan1 == vlan2:
            # These tests should pass
            # Ping between same VLANs
            for setting in offload_settings:
                for offload in setting:
                    m1.run("ethtool -K %s %s %s" % (m1.get_devname("eth1"),
                                                    offload[0], offload[1]))
                    m2.run("ethtool -K %s %s %s" % (m2.get_devname("eth1"),
                                                    offload[0], offload[1]))

                if ipv in [ 'ipv4', 'both' ]:
                    # Ping test
                    m1.run(ping_mod)

                    # Netperf test (both TCP and UDP)
                    srv_proc = m1.run(netperf_srv, bg=True)
                    ctl.wait(2)

                    # prepare PerfRepo result for tcp
                    result_tcp = perf_api.new_result("tcp_ipv4_id",
                                                     "tcp_ipv4_result",
                                                     hash_ignore=[
                                                         'kernel_release',
                                                         'redhat_release'])
                    for offload in setting:
                        result_tcp.set_parameter(offload[0], offload[1])
                    result_tcp.set_parameter('netperf_server_on_vlan', vlan1)
                    result_tcp.set_parameter('netperf_client_on_vlan', vlan2)
                    result_tcp.add_tag(product_name)

                    baseline = perf_api.get_baseline_of_result(result_tcp)
                    netperf_baseline_template(netperf_cli_tcp, baseline)

                    tcp_res_data = m2.run(netperf_cli_tcp,
                                          timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

                    netperf_result_template(result_tcp, tcp_res_data)
                    perf_api.save_result(result_tcp)

                    result_udp = perf_api.new_result("udp_ipv4_id",
                                                     "udp_ipv4_result",
                                                     hash_ignore=[
                                                         'kernel_release',
                                                         'redhat_release'])
                    for offload in setting:
                        result_udp.set_parameter(offload[0], offload[1])
                    result_udp.set_parameter('netperf_server_on_vlan', vlan1)
                    result_udp.set_parameter('netperf_client_on_vlan', vlan2)
                    result_udp.add_tag(product_name)

                    baseline = perf_api.get_baseline_of_result(result_udp)
                    netperf_baseline_template(netperf_cli_udp, baseline)

                    udp_res_data = m2.run(netperf_cli_udp,
                                          timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

                    netperf_result_template(result_udp, udp_res_data)
                    perf_api.save_result(result_udp)

                    srv_proc.intr()

                if ipv in [ 'ipv6', 'both' ]:
                    # Ping test
                    m1.run(ping_mod6)

                    # Netperf test (both TCP and UDP)
                    srv_proc = m1.run(netperf_srv6, bg=True)
                    ctl.wait(2)

                    # prepare PerfRepo result for tcp ipv6
                    result_tcp = perf_api.new_result("tcp_ipv6_id",
                                                     "tcp_ipv6_result",
                                                     hash_ignore=[
                                                         'kernel_release',
                                                         'redhat_release'])
                    for offload in setting:
                        result_tcp.set_parameter(offload[0], offload[1])
                    result_tcp.set_parameter('netperf_server_on_vlan', vlan1)
                    result_tcp.set_parameter('netperf_client_on_vlan', vlan2)
                    result_tcp.set_tag(product_name)

                    baseline = perf_api.get_baseline_of_result(result_tcp)
                    netperf_baseline_template(netperf_cli_tcp6, baseline)

                    tcp_res_data = m2.run(netperf_cli_tcp6,
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
                    result_udp.set_parameter('netperf_server_on_vlan', vlan1)
                    result_udp.set_parameter('netperf_client_on_vlan', vlan2)
                    result_udp.set_tag(product_name)

                    baseline = perf_api.get_baseline_of_result(result_udp)
                    netperf_baseline_template(netperf_cli_udp6, baseline)

                    udp_res_data = m2.run(netperf_cli_udp6,
                                          timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

                    netperf_result_template(result_udp, udp_res_data)
                    perf_api.save_result(result_udp)

                    srv_proc.intr()

        # These tests should fail
        # Ping across different VLAN
        else:
            if ipv in [ 'ipv4', 'both' ]:
                m1.run(ping_mod, expect="fail")

            if ipv in [ 'ipv6', 'both' ]:
                m1.run(ping_mod6, expect="fail")

#reset offload states
for offload in offloads:
    m1.run("ethtool -K %s %s %s" % (m1.get_devname("eth1"),
                                    offload, "on"))
    m2.run("ethtool -K %s %s %s" % (m2.get_devname("eth1"),
                                    offload, "on"))
