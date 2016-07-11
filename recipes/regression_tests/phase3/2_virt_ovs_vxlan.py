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

# hosts
host1 = ctl.get_host("h1")
host2 = ctl.get_host("h2")

# guest machines
guest1 = ctl.get_host("test_host1")
guest2 = ctl.get_host("test_host2")
guest3 = ctl.get_host("test_host3")
guest4 = ctl.get_host("test_host4")

for h in [guest1, guest2, guest3, guest4]:
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
nperf_cpupin = ctl.get_alias("nperf_cpupin")
nperf_cpu_util = ctl.get_alias("nperf_cpu_util")
nperf_num_parallel = int(ctl.get_alias("nperf_num_parallel"))
nperf_debug = ctl.get_alias("nperf_debug")
nperf_max_dev = ctl.get_alias("nperf_max_dev")
pr_user_comment = ctl.get_alias("perfrepo_comment")

pr_comment = generate_perfrepo_comment([guest1, guest2, guest3, guest4],
                                       pr_user_comment)

g1_nic = guest1.get_interface("if1")
g2_nic = guest2.get_interface("if1")
g3_nic = guest3.get_interface("if1")
g4_nic = guest4.get_interface("if1")

g1_nic.set_mtu(mtu)
g2_nic.set_mtu(mtu)
g3_nic.set_mtu(mtu)
g4_nic.set_mtu(mtu)

if nperf_cpupin:
    host1.run("service irqbalance stop")
    host2.run("service irqbalance stop")
    guest1.run("service irqbalance stop")
    guest2.run("service irqbalance stop")
    guest3.run("service irqbalance stop")
    guest4.run("service irqbalance stop")
    h1_if = host1.get_interface("if1")
    h2_if = host2.get_interface("if1")

    #this will pin devices irqs to cpu #0
    for m, d in [(host1, h1_if), (host2, h2_if), (guest1, g1_nic), (guest2, g2_nic), (guest3, g3_nic), (guest4, g4_nic)]:
        pin_dev_irqs(m, d, 0)

nperf_opts = ""
if nperf_cpupin and nperf_num_parallel == 1:
    nperf_opts = " -T%s,%s" % (nperf_cpupin, nperf_cpupin)

ctl.wait(15)

#pings
ping_opts = {"count": 100, "interval": 0.1}
if ipv in ['ipv4', 'both']:
    ping((guest1, g1_nic, 0, {"scope": 0}),
         (guest2, g2_nic, 0, {"scope": 0}),
         options=ping_opts, expect="fail")
    ping((guest1, g1_nic, 0, {"scope": 0}),
         (guest3, g3_nic, 0, {"scope": 0}),
         options=ping_opts)
    ping((guest1, g1_nic, 0, {"scope": 0}),
         (guest4, g4_nic, 0, {"scope": 0}),
         options=ping_opts, expect="fail")

    ping((guest2, g2_nic, 0, {"scope": 0}),
         (guest3, g3_nic, 0, {"scope": 0}),
         options=ping_opts, expect="fail")
    ping((guest2, g2_nic, 0, {"scope": 0}),
         (guest4, g4_nic, 0, {"scope": 0}),
         options=ping_opts)

    ping((guest3, g3_nic, 0, {"scope": 0}),
         (guest4, g4_nic, 0, {"scope": 0}),
         options=ping_opts, expect="fail")

if ipv in ['ipv6', 'both']:
    ping6((guest1, g1_nic, 1, {"scope": 0}),
          (guest2, g2_nic, 1, {"scope": 0}),
          options=ping_opts, expect="fail")
    ping6((guest1, g1_nic, 1, {"scope": 0}),
          (guest3, g3_nic, 1, {"scope": 0}),
          options=ping_opts)
    ping6((guest1, g1_nic, 1, {"scope": 0}),
          (guest4, g4_nic, 1, {"scope": 0}),
          options=ping_opts, expect="fail")

    ping6((guest2, g2_nic, 1, {"scope": 0}),
          (guest3, g3_nic, 1, {"scope": 0}),
          options=ping_opts, expect="fail")
    ping6((guest2, g2_nic, 1, {"scope": 0}),
          (guest4, g4_nic, 1, {"scope": 0}),
          options=ping_opts)

    ping6((guest3, g3_nic, 1, {"scope": 0}),
          (guest4, g4_nic, 1, {"scope": 0}),
          options=ping_opts, expect="fail")


if ipv in [ 'ipv4', 'both' ]:
    # prepare PerfRepo result for tcp
    result_tcp = perf_api.new_result("tcp_ipv4_id",
                                     "tcp_ipv4_result",
                                     hash_ignore=[
                                         r'kernel_release',
                                         r'redhat_release',
                                         r'test_host\d+\.hostname',
                                         r'test_host\d+\..*hwaddr',
                                         r'machine_h\d+\..*ovs\d*\.hwaddr',
                                         r'machine_h\d+\..*tap\d*\.hwaddr',
                                         r'machine_h\d+\..*tap\d*\.devname'])
    result_tcp.add_tag(product_name)
    if nperf_num_parallel > 1:
        result_tcp.add_tag("multithreaded")
        result_tcp.set_parameter('num_parallel', nperf_num_parallel)

    baseline = perf_api.get_baseline_of_result(result_tcp)
    baseline = perfrepo_baseline_to_dict(baseline)

    tcp_res_data = netperf((guest1, g1_nic, 0), (guest3, g3_nic, 0),
                           client_opts={"duration" : netperf_duration,
                                        "testname" : "TCP_STREAM",
                                        "confidence" : nperf_confidence,
                                        "num_parallel" : nperf_num_parallel,
                                        "cpu_util" : nperf_cpu_util,
                                        "runs": nperf_max_runs,
                                        "netperf_opts": nperf_opts,
                                        "debug": nperf_debug,
                                        "max_deviation": nperf_max_dev},
                           baseline = baseline,
                           timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

    netperf_result_template(result_tcp, tcp_res_data)
    result_tcp.set_comment(pr_comment)
    perf_api.save_result(result_tcp)

    # prepare PerfRepo result for udp
    result_udp = perf_api.new_result("udp_ipv4_id",
                                     "udp_ipv4_result",
                                     hash_ignore=[
                                         r'kernel_release',
                                         r'redhat_release',
                                         r'test_host\d+\.hostname',
                                         r'test_host\d+\..*hwaddr',
                                         r'machine_h\d+\..*ovs\d*\.hwaddr',
                                         r'machine_h\d+\..*tap\d*\.hwaddr',
                                         r'machine_h\d+\..*tap\d*\.devname'])
    result_udp.add_tag(product_name)
    if nperf_num_parallel > 1:
        result_udp.add_tag("multithreaded")
        result_udp.set_parameter('num_parallel', nperf_num_parallel)

    baseline = perf_api.get_baseline_of_result(result_udp)
    baseline = perfrepo_baseline_to_dict(baseline)

    udp_res_data = netperf((guest1, g1_nic, 0), (guest3, g3_nic, 0),
                           client_opts={"duration" : netperf_duration,
                                        "testname" : "UDP_STREAM",
                                        "confidence" : nperf_confidence,
                                        "num_parallel" : nperf_num_parallel,
                                        "cpu_util" : nperf_cpu_util,
                                        "runs": nperf_max_runs,
                                        "netperf_opts": nperf_opts,
                                        "debug": nperf_debug,
                                        "max_deviation": nperf_max_dev},
                           baseline = baseline,
                           timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

    netperf_result_template(result_udp, udp_res_data)
    result_udp.set_comment(pr_comment)
    perf_api.save_result(result_udp)
if ipv in [ 'ipv6', 'both' ]:
    # prepare PerfRepo result for tcp ipv6
    result_tcp = perf_api.new_result("tcp_ipv6_id",
                                     "tcp_ipv6_result",
                                     hash_ignore=[
                                         r'kernel_release',
                                         r'redhat_release',
                                         r'test_host\d+\.hostname',
                                         r'test_host\d+\..*hwaddr',
                                         r'machine_h\d+\..*ovs\d*\.hwaddr',
                                         r'machine_h\d+\..*tap\d*\.hwaddr',
                                         r'machine_h\d+\..*tap\d*\.devname'])
    result_tcp.add_tag(product_name)
    if nperf_num_parallel > 1:
        result_tcp.add_tag("multithreaded")
        result_tcp.set_parameter('num_parallel', nperf_num_parallel)

    baseline = perf_api.get_baseline_of_result(result_tcp)
    baseline = perfrepo_baseline_to_dict(baseline)

    tcp_res_data = netperf((guest1, g1_nic, 1), (guest3, g3_nic, 1),
                           client_opts={"duration" : netperf_duration,
                                        "testname" : "TCP_STREAM",
                                        "confidence" : nperf_confidence,
                                        "num_parallel" : nperf_num_parallel,
                                        "cpu_util" : nperf_cpu_util,
                                        "runs": nperf_max_runs,
                                        "netperf_opts" : nperf_opts + "-6",
                                        "debug": nperf_debug,
                                        "max_deviation": nperf_max_dev},
                           baseline = baseline,
                           timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

    netperf_result_template(result_tcp, tcp_res_data)
    result_tcp.set_comment(pr_comment)
    perf_api.save_result(result_tcp)

    #prepare PerfRepo result for udp ipv6
    result_udp = perf_api.new_result("udp_ipv6_id",
                                     "udp_ipv6_result",
                                     hash_ignore=[
                                         r'kernel_release',
                                         r'redhat_release',
                                         r'test_host\d+\.hostname',
                                         r'test_host\d+\..*hwaddr',
                                         r'machine_h\d+\..*ovs\d*\.hwaddr',
                                         r'machine_h\d+\..*tap\d*\.hwaddr',
                                         r'machine_h\d+\..*tap\d*\.devname'])
    result_udp.add_tag(product_name)
    if nperf_num_parallel > 1:
        result_udp.add_tag("multithreaded")
        result_udp.set_parameter('num_parallel', nperf_num_parallel)

    baseline = perf_api.get_baseline_of_result(result_udp)
    baseline = perfrepo_baseline_to_dict(baseline)

    udp_res_data = netperf((guest1, g1_nic, 1), (guest3, g3_nic, 1),
                           client_opts={"duration" : netperf_duration,
                                        "testname" : "UDP_STREAM",
                                        "confidence" : nperf_confidence,
                                        "num_parallel" : nperf_num_parallel,
                                        "cpu_util" : nperf_cpu_util,
                                        "runs": nperf_max_runs,
                                        "netperf_opts" : nperf_opts + "-6",
                                        "debug": nperf_debug,
                                        "max_deviation": nperf_max_dev},
                           baseline = baseline,
                           timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

    netperf_result_template(result_udp, udp_res_data)
    result_udp.set_comment(pr_comment)
    perf_api.save_result(result_udp)

if nperf_cpupin:
    host1.run("service irqbalance start")
    host2.run("service irqbalance start")
    guest1.run("service irqbalance start")
    guest2.run("service irqbalance start")
    guest3.run("service irqbalance start")
    guest4.run("service irqbalance start")
