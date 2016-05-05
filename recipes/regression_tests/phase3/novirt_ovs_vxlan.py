from lnst.Controller.Task import ctl
from lnst.Controller.PerfRepoUtils import perfrepo_baseline_to_dict
from lnst.Controller.PerfRepoUtils import netperf_result_template

from lnst.RecipeCommon.ModuleWrap import ping, ping6, netperf
from lnst.RecipeCommon.IRQ import pin_dev_irqs
from lnst.RecipeCommon.PerfRepo import generate_perfrepo_comment

# ------
# SETUP
# ------

mapping_file = ctl.get_alias("mapping_file")
perf_api = ctl.connect_PerfRepo(mapping_file)

product_name = ctl.get_alias("product_name")

# test hosts
h1 = ctl.get_host("test_host1")
h2 = ctl.get_host("test_host2")

for h in [h1, h2]:
    h.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Netperf"])

# ------
# TESTS
# ------

ipv = ctl.get_alias("ipv")
mtu = ctl.get_alias("mtu")
netperf_duration = int(ctl.get_alias("netperf_duration"))
nperf_reserve = int(ctl.get_alias("nperf_reserve"))
nperf_confidence = ctl.get_alias("nperf_confidence")
nperf_max_runs = int(ctl.get_alias("nperf_max_runs"))
nperf_cpu_util = ctl.get_alias("nperf_cpu_util")
nperf_mode = ctl.get_alias("nperf_mode")
nperf_num_parallel = int(ctl.get_alias("nperf_num_parallel"))
pr_user_comment = ctl.get_alias("perfrepo_comment")

pr_comment = generate_perfrepo_comment([h1, h2], pr_user_comment)

h1_nic = h1.get_device("int0")
h2_nic = h2.get_device("int0")

h1_nic.set_mtu(mtu)
h2_nic.set_mtu(mtu)

h1.run("service irqbalance stop")
h2.run("service irqbalance stop")

# this will pin devices irqs to cpu #0
for m, d in [(h1, h1_nic), (h2, h2_nic)]:
    pin_dev_irqs(m, d, 0)

# if nperf_mode == "multi":
    # netperf_cli_tcp.unset_option("confidence")
    # netperf_cli_udp.unset_option("confidence")
    # netperf_cli_tcp6.unset_option("confidence")
    # netperf_cli_udp6.unset_option("confidence")

    # netperf_cli_tcp.update_options({"num_parallel": nperf_num_parallel})
    # netperf_cli_udp.update_options({"num_parallel": nperf_num_parallel})
    # netperf_cli_tcp6.update_options({"num_parallel": nperf_num_parallel})
    # netperf_cli_udp6.update_options({"num_parallel": nperf_num_parallel})

ctl.wait(15)

#pings
ping_opts = {"count": 100, "interval": 0.1}
if ipv in [ 'ipv4', 'both' ]:
    ping((h1, h1_nic, 0, {"scope": 0}),
         (h2, h2_nic, 0, {"scope": 0}),
         options=ping_opts)

if ipv in [ 'ipv6', 'both' ]:
    ping6((h1, h1_nic, 1, {"scope": 0}),
          (h2, h2_nic, 1, {"scope": 0}),
          options=ping_opts)

#netperfs
if ipv in [ 'ipv4', 'both' ]:
    ctl.wait(2)

    # prepare PerfRepo result for tcp
    result_tcp = perf_api.new_result("tcp_ipv4_id",
                                     "tcp_ipv4_result",
                                     hash_ignore=[
                                         'kernel_release',
                                         'redhat_release'])
    result_tcp.add_tag(product_name)
    if nperf_mode == "multi":
        result_tcp.add_tag("multithreaded")
        result_tcp.set_parameter('num_parallel', nperf_num_parallel)

    baseline = perf_api.get_baseline_of_result(result_tcp)
    baseline = perfrepo_baseline_to_dict(baseline)

    tcp_res_data = netperf((h1, h1_nic, 0, {"scope": 0}),
                           (h2, h2_nic, 0, {"scope": 0}),
                           client_opts={"duration" : netperf_duration,
                                        "testname" : "TCP_STREAM",
                                        "confidence" : nperf_confidence,
                                        "cpu_util" : nperf_cpu_util,
                                        "runs": nperf_max_runs},
                           baseline = baseline,
                           timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

    netperf_result_template(result_tcp, tcp_res_data)
    result_tcp.set_comment(pr_comment)
    perf_api.save_result(result_tcp)

    # prepare PerfRepo result for udp
    result_udp = perf_api.new_result("udp_ipv4_id",
                                     "udp_ipv4_result",
                                     hash_ignore=[
                                         'kernel_release',
                                         'redhat_release'])
    result_udp.add_tag(product_name)
    if nperf_mode == "multi":
        result_udp.add_tag("multithreaded")
        result_udp.set_parameter('num_parallel', nperf_num_parallel)

    baseline = perf_api.get_baseline_of_result(result_udp)
    baseline = perfrepo_baseline_to_dict(baseline)

    udp_res_data = netperf((h1, h1_nic, 0, {"scope": 0}),
                           (h2, h2_nic, 0, {"scope": 0}),
                           client_opts={"duration" : netperf_duration,
                                        "testname" : "UDP_STREAM",
                                        "confidence" : nperf_confidence,
                                        "cpu_util" : nperf_cpu_util,
                                        "runs": nperf_max_runs},
                           baseline = baseline,
                           timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

    netperf_result_template(result_udp, udp_res_data)
    result_udp.set_comment(pr_comment)
    perf_api.save_result(result_udp)
if ipv in [ 'ipv6', 'both' ]:
    ctl.wait(2)

    # prepare PerfRepo result for tcp ipv6
    result_tcp = perf_api.new_result("tcp_ipv6_id",
                                     "tcp_ipv6_result",
                                     hash_ignore=[
                                         'kernel_release',
                                         'redhat_release'])
    result_tcp.add_tag(product_name)
    if nperf_mode == "multi":
        result_tcp.add_tag("multithreaded")
        result_tcp.set_parameter('num_parallel', nperf_num_parallel)

    baseline = perf_api.get_baseline_of_result(result_tcp)
    baseline = perfrepo_baseline_to_dict(baseline)

    tcp_res_data = netperf((h1, h1_nic, 1, {"scope": 0}),
                           (h2, h2_nic, 1, {"scope": 0}),
                           client_opts={"duration" : netperf_duration,
                                        "testname" : "TCP_STREAM",
                                        "confidence" : nperf_confidence,
                                        "cpu_util" : nperf_cpu_util,
                                        "runs": nperf_max_runs,
                                        "netperf_opts" : "-6"},
                           baseline = baseline,
                           timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

    netperf_result_template(result_tcp, tcp_res_data)
    result_tcp.set_comment(pr_comment)
    perf_api.save_result(result_tcp)

    # prepare PerfRepo result for udp ipv6
    result_udp = perf_api.new_result("udp_ipv6_id",
                                     "udp_ipv6_result",
                                     hash_ignore=[
                                         'kernel_release',
                                         'redhat_release'])
    result_udp.add_tag(product_name)
    if nperf_mode == "multi":
        result_udp.add_tag("multithreaded")
        result_udp.set_parameter('num_parallel', nperf_num_parallel)

    baseline = perf_api.get_baseline_of_result(result_udp)
    baseline = perfrepo_baseline_to_dict(baseline)

    udp_res_data = netperf((h1, h1_nic, 1, {"scope": 0}),
                           (h2, h2_nic, 1, {"scope": 0}),
                           client_opts={"duration" : netperf_duration,
                                        "testname" : "UDP_STREAM",
                                        "confidence" : nperf_confidence,
                                        "cpu_util" : nperf_cpu_util,
                                        "runs": nperf_max_runs,
                                        "netperf_opts" : "-6"},
                           baseline = baseline,
                           timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

    netperf_result_template(result_udp, udp_res_data)
    result_udp.set_comment(pr_comment)
    perf_api.save_result(result_udp)

h1.run("service irqbalance start")
h2.run("service irqbalance start")
