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

m1 = ctl.get_host("machine1")
m2 = ctl.get_host("machine2")

m1.sync_resources(modules=["Netperf", "Custom"])
m2.sync_resources(modules=["Netperf", "Custom"])

# ------
# TESTS
# ------

ipv = ctl.get_alias("ipv")
mtu = ctl.get_alias("mtu")
netperf_duration = int(ctl.get_alias("netperf_duration"))
nperf_reserve = int(ctl.get_alias("nperf_reserve"))
nperf_confidence = ctl.get_alias("nperf_confidence")
nperf_max_runs = int(ctl.get_alias("nperf_max_runs"))
nperf_cpupin = ctl.get_alias("nperf_cpupin")
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
adaptive_coalescing_off = bool_it(ctl.get_alias("adaptive_coalescing_off"))

sctp_default_msg_size = "16K"

if offloads_alias is not None:
    offloads, offload_settings = parse_offloads(offloads_alias)
else:
    offloads = ["gro", "gso", "tso", "tx", "rx"]
    offload_settings = [ [("gro", "on"), ("gso", "on"), ("tso", "on"), ("tx", "on"), ("rx", "on")],
                         [("gro", "off"), ("gso", "on"), ("tso", "on"), ("tx", "on"), ("rx", "on")],
                         [("gro", "on"), ("gso", "off"),  ("tso", "off"), ("tx", "on"), ("rx", "on")],
                         [("gro", "on"), ("gso", "on"), ("tso", "off"), ("tx", "off"), ("rx", "on")],
                         [("gro", "on"), ("gso", "on"), ("tso", "on"), ("tx", "on"), ("rx", "off")]]

pr_comment = generate_perfrepo_comment([m1, m2], pr_user_comment)

m1_testiface = m1.get_interface("testiface")
m2_testiface = m2.get_interface("testiface")

m1_testiface.set_mtu(mtu)
m2_testiface.set_mtu(mtu)

if adaptive_coalescing_off:
    coalesce_status = ctl.get_module('Custom')

    for d in [ m1_testiface, m2_testiface ]:
        # disable any interrupt coalescing settings
        cdata = d.save_coalesce()
        cdata['use_adaptive_tx_coalesce'] = 0
        cdata['use_adaptive_rx_coalesce'] = 0
        if not d.set_coalesce(cdata):
            coalesce_status.set_options({'fail': True,
                                         'msg': "Failed to set coalesce options"\
                                                " on device %s" % d.get_devname()})
            d.get_host().run(coalesce_status)

if nperf_cpupin:
    m1.run("service irqbalance stop")
    m2.run("service irqbalance stop")

    for m, d in [ (m1, m1_testiface), (m2, m2_testiface) ]:
        pin_dev_irqs(m, d, 0)

p_opts = "-L %s" % (m2_testiface.get_ip(0))
if nperf_cpupin and nperf_mode != "multi":
    p_opts += " -T%s,%s" % (nperf_cpupin, nperf_cpupin)

p_opts6 = "-L %s -6" % (m2_testiface.get_ip(1))
if nperf_cpupin and nperf_mode != "multi":
    p_opts6 += " -T%s,%s" % (nperf_cpupin, nperf_cpupin)

netperf_cli_tcp = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" : m1_testiface.get_ip(0),
                                      "duration" : netperf_duration,
                                      "testname" : "TCP_STREAM",
                                      "confidence" : nperf_confidence,
                                      "cpu_util" : nperf_cpu_util,
                                      "runs" : nperf_max_runs,
                                      "netperf_opts" : p_opts,
                                      "debug" : nperf_debug,
                                      "max_deviation" : nperf_max_dev
                                  })

netperf_cli_tcp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" : m1_testiface.get_ip(1),
                                      "duration" : netperf_duration,
                                      "testname" : "TCP_STREAM",
                                      "confidence" : nperf_confidence,
                                      "cpu_util" : nperf_cpu_util,
                                      "runs" : nperf_max_runs,
                                      "netperf_opts" : p_opts6,
                                      "debug" : nperf_debug,
                                      "max_deviation" : nperf_max_dev
                                  })

netperf_cli_udp = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" : m1_testiface.get_ip(0),
                                      "duration" : netperf_duration,
                                      "testname" : "UDP_STREAM",
                                      "confidence" : nperf_confidence,
                                      "cpu_util" : nperf_cpu_util,
                                      "runs" : nperf_max_runs,
                                      "netperf_opts" : p_opts,
                                      "debug" : nperf_debug,
                                      "max_deviation" : nperf_max_dev
                                  })

netperf_cli_udp6 = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" : m1_testiface.get_ip(1),
                                      "duration" : netperf_duration,
                                      "testname" : "UDP_STREAM",
                                      "confidence" : nperf_confidence,
                                      "cpu_util" : nperf_cpu_util,
                                      "runs" : nperf_max_runs,
                                      "netperf_opts" : p_opts6,
                                      "debug" : nperf_debug,
                                      "max_deviation" : nperf_max_dev
                                  })

netperf_cli_sctp = ctl.get_module("Netperf",
                                  options={
                                      "role" : "client",
                                      "netperf_server" : m1_testiface.get_ip(0),
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
                                      "netperf_server" : m1_testiface.get_ip(1),
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

netperf_srv = ctl.get_module("Netperf",
                              options={
                                  "role" : "server",
                                  "bind" : m1_testiface.get_ip(0)
                                  })

netperf_srv6 = ctl.get_module("Netperf",
                              options={
                                  "role" : "server",
                                  "bind" : m1_testiface.get_ip(1)
                                  })

if nperf_mode == "multi":
    netperf_cli_tcp.unset_option("confidence")
    netperf_cli_udp.unset_option("confidence")
    netperf_cli_sctp.unset_option("confidence")
    netperf_cli_tcp6.unset_option("confidence")
    netperf_cli_udp6.unset_option("confidence")
    netperf_cli_sctp6.unset_option("confidence")

    netperf_cli_tcp.update_options({"num_parallel" : nperf_num_parallel})
    netperf_cli_udp.update_options({"num_parallel" : nperf_num_parallel})
    netperf_cli_sctp.update_options({"num_parallel" : nperf_num_parallel})
    netperf_cli_tcp6.update_options({"num_parallel" : nperf_num_parallel})
    netperf_cli_udp6.update_options({"num_parallel" : nperf_num_parallel})
    netperf_cli_sctp6.update_options({"num_parallel" : nperf_num_parallel})

    # we have to use multiqueue qdisc to get appropriate data
    m1.run("tc qdisc replace dev %s root mq" % m1_testiface.get_devname())
    m2.run("tc qdisc replace dev %s root mq" % m2_testiface.get_devname())

if nperf_msg_size is not None:
    netperf_cli_tcp.update_options({"msg_size" : nperf_msg_size})
    netperf_cli_udp.update_options({"msg_size" : nperf_msg_size})
    netperf_cli_sctp.update_options({"msg_size" : nperf_msg_size})
    netperf_cli_tcp6.update_options({"msg_size" : nperf_msg_size})
    netperf_cli_udp6.update_options({"msg_size" : nperf_msg_size})
    netperf_cli_sctp6.update_options({"msg_size" : nperf_msg_size})

# if we will run SCTP test make sure the SCTP will go out through the test
# interfaces only
if nperf_protocols.find("sctp") > -1:
    m1.run("iptables -I OUTPUT ! -o %s -p sctp -j DROP" %
            m1_testiface.get_devname())
    m2.run("iptables -I OUTPUT ! -o %s -p sctp -j DROP" %
            m2_testiface.get_devname())

ctl.wait(15)

for setting in offload_settings:
    dev_features = ""
    for offload in setting:
        dev_features += " %s %s" % (offload[0], offload[1])
    m1.run("ethtool -K %s %s" % (m1_testiface.get_devname(), dev_features))
    m2.run("ethtool -K %s %s" % (m2_testiface.get_devname(), dev_features))

    if ("rx", "off") in setting:
        # when rx offload is turned off some of the cards might get reset
        # and link goes down, so wait a few seconds until NIC is ready
        ctl.wait(15)

    # Netperf test
    if ipv in [ 'ipv4', 'both' ]:
        srv_proc = m1.run(netperf_srv, bg=True)
        ctl.wait(2)

        if nperf_protocols.find("tcp") > -1:
            # prepare PerfRepo result for tcp
            result_tcp = perf_api.new_result("tcp_ipv4_id",
                                             "tcp_ipv4_result",
                                             hash_ignore=[
                                                 'kernel_release',
                                                 'redhat_release'])
            for offload in setting:
                result_tcp.set_parameter(offload[0], offload[1])

            if nperf_msg_size is not None:
                result_tcp.set_parameter("nperf_msg_size", nperf_msg_size)

            result_tcp.add_tag(product_name)
            if nperf_mode == "multi":
                result_tcp.add_tag("multithreaded")
                result_tcp.set_parameter("num_parallel", nperf_num_parallel)

            baseline = perf_api.get_baseline_of_result(result_tcp)
            netperf_baseline_template(netperf_cli_tcp, baseline)
            tcp_res_data = m2.run(netperf_cli_tcp,
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
                                                 'redhat_release'])
            for offload in setting:
                result_udp.set_parameter(offload[0], offload[1])

            if nperf_msg_size is not None:
                result_udp.set_parameter("nperf_msg_size", nperf_msg_size)

            result_udp.add_tag(product_name)
            if nperf_mode == "multi":
                result_udp.add_tag("multithreaded")
                result_udp.set_parameter("num_parallel", nperf_num_parallel)

            baseline = perf_api.get_baseline_of_result(result_udp)
            netperf_baseline_template(netperf_cli_udp, baseline)
            udp_res_data = m2.run(netperf_cli_udp,
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
                                                  'redhat_release'])
            for offload in setting:
                result_sctp.set_parameter(offload[0], offload[1])

            if nperf_msg_size is not None:
                result_sctp.set_parameter("nperf_msg_size", nperf_msg_size)

            result_sctp.add_tag(product_name)
            if nperf_mode == "multi":
                result_sctp.add_tag("multithreaded")
                result_sctp.set_parameter("num_parallel", nperf_num_parallel)

            baseline = perf_api.get_baseline_of_result(result_sctp)
            netperf_baseline_template(netperf_cli_sctp, baseline)
            sctp_res_data = m2.run(netperf_cli_sctp,
                                   timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

            netperf_result_template(result_sctp, sctp_res_data)
            result_sctp.set_comment(pr_comment)
            perf_api.save_result(result_sctp, official_result)

        srv_proc.intr()

    if ipv in [ 'ipv6', 'both' ]:
        srv_proc = m1.run(netperf_srv6, bg=True)
        ctl.wait(2)

        if nperf_protocols.find("tcp") > -1:
            # prepare PerfRepo result for tcp ipv6
            result_tcp = perf_api.new_result("tcp_ipv6_id",
                                             "tcp_ipv6_result",
                                             hash_ignore=[
                                                 'kernel_release',
                                                 'redhat_release'])
            for offload in setting:
                result_tcp.set_parameter(offload[0], offload[1])

            if nperf_msg_size is not None:
                result_tcp.set_parameter("nperf_msg_size", nperf_msg_size)

            result_tcp.add_tag(product_name)
            if nperf_mode == "multi":
                result_tcp.add_tag("multithreaded")
                result_tcp.set_parameter("num_parallel", nperf_num_parallel)

            baseline = perf_api.get_baseline_of_result(result_tcp)
            netperf_baseline_template(netperf_cli_tcp6, baseline)
            tcp_res_data = m2.run(netperf_cli_tcp6,
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
                                                 'redhat_release'])
            for offload in setting:
                result_udp.set_parameter(offload[0], offload[1])

            if nperf_msg_size is not None:
                result_udp.set_parameter("nperf_msg_size", nperf_msg_size)

            result_udp.add_tag(product_name)
            if nperf_mode == "multi":
                result_udp.add_tag("multithreaded")
                result_udp.set_parameter("num_parallel", nperf_num_parallel)

            baseline = perf_api.get_baseline_of_result(result_udp)
            netperf_baseline_template(netperf_cli_udp6, baseline)
            udp_res_data = m2.run(netperf_cli_udp6,
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
                                                  'redhat_release'])
            for offload in setting:
                result_sctp.set_parameter(offload[0], offload[1])

            if nperf_msg_size is not None:
                result_sctp.set_parameter("nperf_msg_size", nperf_msg_size)

            result_sctp.add_tag(product_name)
            if nperf_mode == "multi":
                result_sctp.add_tag("multithreaded")
                result_sctp.set_parameter("num_parallel", nperf_num_parallel)

            baseline = perf_api.get_baseline_of_result(result_sctp)
            netperf_baseline_template(netperf_cli_sctp6, baseline)
            sctp_res_data = m2.run(netperf_cli_sctp6,
                                   timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

            netperf_result_template(result_sctp, sctp_res_data)
            result_sctp.set_comment(pr_comment)
            perf_api.save_result(result_sctp, official_result)

        srv_proc.intr()

# reset offload states
dev_features = ""
for offload in offloads:
    dev_features += " %s %s" % (offload, "on")

m1.run("ethtool -K %s %s" % (m1_testiface.get_devname(), dev_features))
m2.run("ethtool -K %s %s" % (m2_testiface.get_devname(), dev_features))

if nperf_cpupin:
    m1.run("service irqbalance start")
    m2.run("service irqbalance start")

if nperf_protocols.find("sctp") > -1:
    m1.run("iptables -D OUTPUT ! -o %s -p sctp -j DROP" %
            m1_testiface.get_devname())
    m2.run("iptables -D OUTPUT ! -o %s -p sctp -j DROP" %
            m2_testiface.get_devname())

if adaptive_coalescing_off:
    for d in [ m1_testiface, m2_testiface ]:
        # restore any interrupt coalescing settings
        d.restore_coalesce()
