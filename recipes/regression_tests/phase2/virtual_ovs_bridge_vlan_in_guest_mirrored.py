from lnst.Common.Utils import bool_it
from lnst.Controller.Task import ctl
from lnst.Controller.PerfRepoUtils import netperf_baseline_template
from lnst.Controller.PerfRepoUtils import netperf_result_template

from lnst.RecipeCommon.IRQ import pin_dev_irqs
from lnst.RecipeCommon.PerfRepo import generate_perfrepo_comment
from lnst.RecipeCommon.Offloads import parse_offloads

# ------
# SETUP
# ------

mapping_file = ctl.get_alias("mapping_file")
perf_api = ctl.connect_PerfRepo(mapping_file)

product_name = ctl.get_alias("product_name")

h1 = ctl.get_host("host1")
g1 = ctl.get_host("guest1")

h2 = ctl.get_host("host2")
g2 = ctl.get_host("guest2")

g1.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Netperf"])
g2.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Netperf"])

# ------
# TESTS
# ------

mtu = ctl.get_alias("mtu")
ipv = ctl.get_alias("ipv")
netperf_duration = int(ctl.get_alias("netperf_duration"))
nperf_reserve = int(ctl.get_alias("nperf_reserve"))
nperf_confidence = ctl.get_alias("nperf_confidence")
nperf_max_runs = int(ctl.get_alias("nperf_max_runs"))
nperf_cpu_util = ctl.get_alias("nperf_cpu_util")
nperf_mode = ctl.get_alias("nperf_mode")
nperf_num_parallel = int(ctl.get_alias("nperf_num_parallel"))
nperf_debug = ctl.get_alias("nperf_debug")
nperf_max_dev = ctl.get_alias("nperf_max_dev")
nperf_msg_size = ctl.get_alias("nperf_msg_size")
pr_user_comment = ctl.get_alias("perfrepo_comment")
offloads_alias = ctl.get_alias("offloads")
nperf_protocols = ctl.get_alias("nperf_protocols")
official_result = bool_it(ctl.get_alias("official_result"))

sctp_default_msg_size = "16K"

if offloads_alias is not None:
    offloads, offload_settings = parse_offloads(offloads_alias)
else:
    offloads = ["gro", "gso", "tso", "rx", "tx"]
    offload_settings = [ [("gro", "on"), ("gso", "on"), ("tso", "on"), ("tx", "on"), ("rx", "on")],
                         [("gro", "off"), ("gso", "on"), ("tso", "on"), ("tx", "on"), ("rx", "on")],
                         [("gro", "on"), ("gso", "off"),  ("tso", "off"), ("tx", "on"), ("rx", "on")],
                         [("gro", "on"), ("gso", "on"), ("tso", "off"), ("tx", "off"), ("rx", "on")],
                         [("gro", "on"), ("gso", "on"), ("tso", "on"), ("tx", "on"), ("rx", "off")]]

pr_comment = generate_perfrepo_comment([h1, g1, h2, g2], pr_user_comment)

g1_vlan10 = g1.get_interface("vlan10")
g2_vlan10 = g2.get_interface("vlan10")
h1_nic = h1.get_interface("nic")
h2_nic = h2.get_interface("nic")
g1_guestnic = g1.get_interface("guestnic")
g2_guestnic = g2.get_interface("guestnic")

h1.run("service irqbalance stop")
h2.run("service irqbalance stop")

# this will pin devices irqs to cpu #0
for m, d in [ (h1, h1_nic), (h2, h2_nic) ]:
    pin_dev_irqs(m, d, 0)

ping_mod = ctl.get_module("IcmpPing",
                           options={
                               "addr" : g2_vlan10.get_ip(0),
                               "count" : 100,
                               "iface" : g1_vlan10.get_devname(),
                               "interval" : 0.1
                           })

ping_mod6 = ctl.get_module("Icmp6Ping",
                           options={
                               "addr" : g2_vlan10.get_ip(1),
                               "count" : 100,
                               "iface" : g1_vlan10.get_ip(1),
                               "interval" : 0.1
                           })

netperf_srv = ctl.get_module("Netperf",
                              options={
                                  "role" : "server",
                                  "bind" : g1_vlan10.get_ip(0)
                              })

netperf_srv6 = ctl.get_module("Netperf",
                              options={
                                  "role" : "server",
                                  "bind" : g1_vlan10.get_ip(1),
                                  "netperf_opts" : " -6",
                              })

p_opts = "-L %s" % (g2_vlan10.get_ip(0))
p_opts6 = "-L %s -6" % (g2_vlan10.get_ip(1))

netperf_cli_tcp = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" : g1_vlan10.get_ip(0),
                                      "duration" : netperf_duration,
                                      "testname" : "TCP_STREAM",
                                      "confidence" : nperf_confidence,
                                      "cpu_util" : nperf_cpu_util,
                                      "runs": nperf_max_runs,
                                      "netperf_opts" : p_opts,
                                      "debug" : nperf_debug,
                                      "max_deviation" : nperf_max_dev
                                  })

netperf_cli_udp = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" : g1_vlan10.get_ip(0),
                                      "duration" : netperf_duration,
                                      "testname" : "UDP_STREAM",
                                      "confidence" : nperf_confidence,
                                      "cpu_util" : nperf_cpu_util,
                                      "runs": nperf_max_runs,
                                      "netperf_opts" : p_opts,
                                      "debug" : nperf_debug,
                                      "max_deviation" : nperf_max_dev
                                  })

netperf_cli_tcp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" :
                                          g1_vlan10.get_ip(1),
                                      "duration" : netperf_duration,
                                      "testname" : "TCP_STREAM",
                                      "confidence" : nperf_confidence,
                                      "cpu_util" : nperf_cpu_util,
                                      "runs": nperf_max_runs,
                                      "netperf_opts" : p_opts6,
                                      "debug" : nperf_debug,
                                      "max_deviation" : nperf_max_dev
                                  })

netperf_cli_udp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" :
                                          g1_vlan10.get_ip(1),
                                      "duration" : netperf_duration,
                                      "testname" : "UDP_STREAM",
                                      "confidence" : nperf_confidence,
                                      "cpu_util" : nperf_cpu_util,
                                      "runs": nperf_max_runs,
                                      "netperf_opts" : p_opts6,
                                      "debug" : nperf_debug,
                                      "max_deviation" : nperf_max_dev
                                  })

netperf_cli_sctp = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" :
                                          g1_vlan10.get_ip(0),
                                      "duration" : netperf_duration,
                                      "testname" : "SCTP_STREAM",
                                      "confidence" : nperf_confidence,
                                      "cpu_util" : nperf_cpu_util,
                                      "runs" : nperf_max_runs,
                                      "netperf_opts" : p_opts,
                                      "msg_size" : sctp_default_msg_size,
                                      "debug" : nperf_debug,
                                      "max_deviation" : nperf_max_dev
                                  })

netperf_cli_sctp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" :
                                          g1_vlan10.get_ip(1),
                                      "duration" : netperf_duration,
                                      "testname" : "SCTP_STREAM",
                                      "confidence" : nperf_confidence,
                                      "cpu_util" : nperf_cpu_util,
                                      "runs" : nperf_max_runs,
                                      "netperf_opts" : p_opts6,
                                      "msg_size" : sctp_default_msg_size,
                                      "debug" : nperf_debug,
                                      "max_deviation" : nperf_max_dev
                                  })

if nperf_mode == "multi":
    netperf_cli_tcp.unset_option("confidence")
    netperf_cli_udp.unset_option("confidence")
    netperf_cli_sctp.unset_option("confidence")
    netperf_cli_tcp6.unset_option("confidence")
    netperf_cli_udp6.unset_option("confidence")
    netperf_cli_sctp6.unset_option("confidence")

    netperf_cli_tcp.update_options({"num_parallel": nperf_num_parallel})
    netperf_cli_udp.update_options({"num_parallel": nperf_num_parallel})
    netperf_cli_sctp.update_options({"num_parallel": nperf_num_parallel})
    netperf_cli_tcp6.update_options({"num_parallel": nperf_num_parallel})
    netperf_cli_udp6.update_options({"num_parallel": nperf_num_parallel})
    netperf_cli_sctp6.update_options({"num_parallel": nperf_num_parallel})

    # we have to use multiqueue qdisc to get appropriate data
    h1.run("tc qdisc replace dev %s root mq" % h1_nic.get_devname())
    h2.run("tc qdisc replace dev %s root mq" % h2_nic.get_devname())

if nperf_msg_size is not None:
    netperf_cli_tcp.update_options({"msg_size" : nperf_msg_size})
    netperf_cli_udp.update_options({"msg_size" : nperf_msg_size})
    netperf_cli_sctp.update_options({"msg_size" : nperf_msg_size})
    netperf_cli_tcp6.update_options({"msg_size" : nperf_msg_size})
    netperf_cli_udp6.update_options({"msg_size" : nperf_msg_size})
    netperf_cli_sctp6.update_options({"msg_size" : nperf_msg_size})

#set mtu
h1.get_interface("nic").set_mtu(mtu)
h1.get_interface("tap").set_mtu(mtu)
h1.get_interface("br").set_mtu(mtu)

h2.get_interface("nic").set_mtu(mtu)
h2.get_interface("tap").set_mtu(mtu)
h2.get_interface("br").set_mtu(mtu)

g1.get_interface("guestnic").set_mtu(mtu)
g1.get_interface("vlan10").set_mtu(mtu)

g2.get_interface("guestnic").set_mtu(mtu)
g2.get_interface("vlan10").set_mtu(mtu)

ctl.wait(15)

for setting in offload_settings:
    dev_features = ""
    for offload in setting:
        dev_features += " %s %s" % (offload[0], offload[1])
    h1.run("ethtool -K %s %s" % (h1_nic.get_devname(), dev_features))
    g1.run("ethtool -K %s %s" % (g1_guestnic.get_devname(), dev_features))
    h2.run("ethtool -K %s %s" % (h2_nic.get_devname(), dev_features))
    g2.run("ethtool -K %s %s" % (g2_guestnic.get_devname(), dev_features))

    if ("rx", "off") in setting:
        # when rx offload is turned off some of the cards might get reset
        # and link goes down, so wait a few seconds until NIC is ready
        ctl.wait(15)

    if ipv in [ 'ipv4', 'both' ]:
        g1.run(ping_mod)

        server_proc = g1.run(netperf_srv, bg=True)
        ctl.wait(2)

        if nperf_protocols.find("tcp") > -1:
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

            if nperf_msg_size is not None:
                result_tcp.set_parameter("nperf_msg_size", nperf_msg_size)

            result_tcp.add_tag(product_name)
            if nperf_mode == "multi":
                result_tcp.add_tag("multithreaded")
                result_tcp.set_parameter('num_parallel', nperf_num_parallel)

            baseline = perf_api.get_baseline_of_result(result_tcp)
            netperf_baseline_template(netperf_cli_tcp, baseline)

            tcp_res_data = g2.run(netperf_cli_tcp,
                                  timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

            netperf_result_template(result_tcp, tcp_res_data)
            result_tcp.set_comment(pr_comment)
            perf_api.save_result(result_tcp, official_result)

        if nperf_protocols.find("udp") > -1 and ("gro", "off") not in setting:
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

            if nperf_msg_size is not None:
                result_udp.set_parameter("nperf_msg_size", nperf_msg_size)

            result_udp.add_tag(product_name)
            if nperf_mode == "multi":
                result_udp.add_tag("multithreaded")
                result_udp.set_parameter('num_parallel', nperf_num_parallel)

            baseline = perf_api.get_baseline_of_result(result_udp)
            netperf_baseline_template(netperf_cli_udp, baseline)

            udp_res_data = g2.run(netperf_cli_udp,
                                  timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

            netperf_result_template(result_udp, udp_res_data)
            result_udp.set_comment(pr_comment)
            perf_api.save_result(result_udp, official_result)

        # for SCTP only gso offload on/off
        if (nperf_protocols.find("sctp") > -1 and
              (len([val for val in setting if val[1] == 'off']) == 0 or
               ('gso', 'off') in setting)):
            result_sctp = perf_api.new_result("sctp_ipv4_id",
                                              "sctp_ipv4_result",
                                              hash_ignore=[
                                                  'kernel_release',
                                                  'redhat_release',
                                                  r'guest\d+\.hostname',
                                                  r'guest\d+\..*hwaddr',
                                                  r'host\d+\..*tap\d*\.hwaddr',
                                                  r'host\d+\..*tap\d*\.devname'])
            for offload in setting:
                result_sctp.set_parameter(offload[0], offload[1])

            result_sctp.add_tag(product_name)
            if nperf_mode == "multi":
                result_sctp.add_tag("multithreaded")
                result_sctp.set_parameter("num_parallel", nperf_num_parallel)

            baseline = perf_api.get_baseline_of_result(result_sctp)
            netperf_baseline_template(netperf_cli_sctp, baseline)
            sctp_res_data = g2.run(netperf_cli_sctp,
                                   timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

            netperf_result_template(result_sctp, sctp_res_data)
            result_sctp.set_comment(pr_comment)
            perf_api.save_result(result_sctp, official_result)

        server_proc.intr()

    if ipv in [ 'ipv6', 'both' ]:
        g1.run(ping_mod6)

        server_proc = g1.run(netperf_srv6, bg=True)
        ctl.wait(2)

        if nperf_protocols.find("tcp") > -1:
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

            if nperf_msg_size is not None:
                result_tcp.set_parameter("nperf_msg_size", nperf_msg_size)

            result_tcp.add_tag(product_name)
            if nperf_mode == "multi":
                result_tcp.add_tag("multithreaded")
                result_tcp.set_parameter('num_parallel', nperf_num_parallel)

            baseline = perf_api.get_baseline_of_result(result_tcp)
            netperf_baseline_template(netperf_cli_tcp6, baseline)

            tcp_res_data = g2.run(netperf_cli_tcp6,
                                  timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

            netperf_result_template(result_tcp, tcp_res_data)
            result_tcp.set_comment(pr_comment)
            perf_api.save_result(result_tcp, official_result)

        if nperf_protocols.find("udp") > -1 and ("gro", "off") not in setting:
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

            if nperf_msg_size is not None:
                result_udp.set_parameter("nperf_msg_size", nperf_msg_size)

            result_udp.add_tag(product_name)
            if nperf_mode == "multi":
                result_udp.add_tag("multithreaded")
                result_udp.set_parameter('num_parallel', nperf_num_parallel)

            baseline = perf_api.get_baseline_of_result(result_udp)
            netperf_baseline_template(netperf_cli_udp6, baseline)

            udp_res_data = g2.run(netperf_cli_udp6,
                                  timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

            netperf_result_template(result_udp, udp_res_data)
            result_udp.set_comment(pr_comment)
            perf_api.save_result(result_udp, official_result)

        # for SCTP only gso offload on/off
        if (nperf_protocols.find("sctp") > -1 and
              (len([val for val in setting if val[1] == 'off']) == 0 or
               ('gso', 'off') in setting)):
            result_sctp = perf_api.new_result("sctp_ipv6_id",
                                              "sctp_ipv6_result",
                                              hash_ignore=[
                                                  'kernel_release',
                                                  'redhat_release',
                                                  r'guest\d+\.hostname',
                                                  r'guest\d+\..*hwaddr',
                                                  r'host\d+\..*tap\d*\.hwaddr',
                                                  r'host\d+\..*tap\d*\.devname'])
            for offload in setting:
                result_sctp.set_parameter(offload[0], offload[1])

            result_sctp.add_tag(product_name)
            if nperf_mode == "multi":
                result_sctp.add_tag("multithreaded")
                result_sctp.set_parameter("num_parallel", nperf_num_parallel)

            baseline = perf_api.get_baseline_of_result(result_sctp)
            netperf_baseline_template(netperf_cli_sctp, baseline)
            sctp_res_data = g2.run(netperf_cli_sctp6,
                                   timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

            netperf_result_template(result_sctp, sctp_res_data)
            result_sctp.set_comment(pr_comment)
            perf_api.save_result(result_sctp, official_result)

        server_proc.intr()

#reset offload states
dev_features = ""
for offload in offloads:
    dev_features += " %s %s" % (offload, "on")
h1.run("ethtool -K %s %s" % (h1_nic.get_devname(), dev_features))
g1.run("ethtool -K %s %s" % (g1_guestnic.get_devname(), dev_features))
h2.run("ethtool -K %s %s" % (h2_nic.get_devname(), dev_features))
g2.run("ethtool -K %s %s" % (g2_guestnic.get_devname(), dev_features))

h1.run("service irqbalance start")
h2.run("service irqbalance start")
