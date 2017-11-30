from lnst.Common.Utils import bool_it
from lnst.Controller.Task import ctl
from lnst.Controller.PerfRepoUtils import perfrepo_baseline_to_dict
from lnst.Controller.PerfRepoUtils import netperf_result_template

from lnst.RecipeCommon.ModuleWrap import netperf
from lnst.RecipeCommon.IRQ import pin_dev_irqs
from lnst.RecipeCommon.PerfRepo import generate_perfrepo_comment

# ---------------------------
# ALGORITHM AND CIPHER CONFIG
# ---------------------------

#lenth param is in bits
def generate_key(length):
    key = "0x"
    key = key + (length/8) * "0b"
    return key

algorithm = []

algorithm.append(('rfc4106(gcm(aes))', 160, 96))

# ------
# SETUP
# ------

mapping_file = ctl.get_alias("mapping_file")
perf_api = ctl.connect_PerfRepo(mapping_file)

product_name = ctl.get_alias("product_name")

m1 = ctl.get_host("machine1")
m2 = ctl.get_host("machine2")

m1.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Netperf", "Custom"])
m2.sync_resources(modules=["PacketAssert", "IcmpPing", "Icmp6Ping", "Netperf"])

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
nperf_msg_size = ctl.get_alias("nperf_msg_size")
pr_user_comment = ctl.get_alias("perfrepo_comment")
ipsec_mode = ctl.get_alias("ipsec_mode")
official_result = bool_it(ctl.get_alias("official_result"))

pr_comment = generate_perfrepo_comment([m1, m2], pr_user_comment)

m1_if = m1.get_interface("eth")
m2_if = m2.get_interface("eth")

m1_if.set_mtu(mtu)
m2_if.set_mtu(mtu)

m1_if_name = m1_if.get_devname()
m2_if_name = m2_if.get_devname()

m1_if_addr = m1_if.get_ip()
m2_if_addr = m2_if.get_ip()

m1_if_addr6 = m1_if.get_ip(1)
m2_if_addr6 = m2_if.get_ip(1)


# add routing rulez ipv4
# so the host knows where to send traffic destined to remote site
m1.run("ip route add %s dev %s" % (m2_if_addr, m1_if_name))

# so the host knows where to send traffic destined to remote site
m2.run("ip route add %s dev %s" % (m1_if_addr, m2_if_name))

# add routing rulez ipv6
# so the host knows where to send traffic destined to remote site
m1.run("ip route add %s dev %s" % (m2_if_addr6, m1_if_name))

# so the host knows where to send traffic destined to remote site
m2.run("ip route add %s dev %s" % (m1_if_addr6, m2_if_name))

if nperf_msg_size is None:
    nperf_msg_size = 16000

if ipsec_mode is None:
    ipsec_mode = "transport"

res = m1.run("rpm -qa iproute", save_output=True)
if (res.get_result()["res_data"]["stdout"].find("iproute-2") != -1):
    m1_key="0x"
else:
    m1_key=""

res = m2.run("rpm -qa iproute", save_output=True)
if (res.get_result()["res_data"]["stdout"].find("iproute-2") != -1):
    m2_key="0x"
else:
    m2_key=""

if nperf_cpupin:
    m1.run("service irqbalance stop")
    m2.run("service irqbalance stop")

    dev_list = [(m1, m1_if), (m2, m2_if)]

    # this will pin devices irqs to cpu #0
    for m, d in dev_list:
        pin_dev_irqs(m, d, 0)

nperf_opts = ""
if nperf_cpupin and nperf_num_parallel == 1:
    nperf_opts = " -T%s,%s" % (nperf_cpupin, nperf_cpupin)

ctl.wait(15)

def configure_ipsec(algo, algo_key, icv_len, ip_version):
    if ip_version == "ipv4":
        m1_addr = m1_if_addr
        m2_addr = m2_if_addr
    else:
        m1_addr = m1_if_addr6
        m2_addr = m2_if_addr6

    # configure policy and state
    m1.run("ip xfrm policy flush")
    m1.run("ip xfrm state flush")
    m2.run("ip xfrm policy flush")
    m2.run("ip xfrm state flush")

    m1.run("ip xfrm state add src %s dst %s proto esp spi 0x1001 "\
           "aead '%s' %s %s mode %s "\
           "sel src %s dst %s"\
           % (m2_addr, m1_addr,
              algo, algo_key, icv_len, ipsec_mode,
              m2_addr, m1_addr))

    m1.run("ip xfrm policy add src %s dst %s dir in tmpl "\
           "src %s dst %s proto esp mode %s action allow"\
           % (m2_addr, m1_addr,
              m2_addr, m1_addr, ipsec_mode))

    m1.run("ip xfrm state add src %s dst %s proto esp spi 0x1000 "\
           "aead '%s' %s %s mode %s "\
           "sel src %s dst %s"\
           % (m1_addr, m2_addr,
              algo, algo_key, icv_len, ipsec_mode,
              m1_addr, m2_addr))

    m1.run("ip xfrm policy add src %s dst %s dir out tmpl "\
           "src %s dst %s proto esp mode %s action allow"\
           % (m1_addr, m2_addr,
              m1_addr, m2_addr, ipsec_mode))




    m2.run("ip xfrm state add src %s dst %s proto esp spi 0x1000 "\
           "aead '%s' %s %s mode %s "\
           "sel src %s dst %s"\
           % (m1_addr, m2_addr,
              algo, algo_key, icv_len, ipsec_mode,
              m1_addr, m2_addr))

    m2.run("ip xfrm policy add src %s dst %s dir in tmpl "\
           "src %s dst %s proto esp mode %s action allow"\
           % (m1_addr, m2_addr,
              m1_addr, m2_addr, ipsec_mode))

    m2.run("ip xfrm state add src %s dst %s proto esp spi 0x1001 "\
           "aead '%s' %s %s mode %s sel "\
           "src %s dst %s"\
           % (m2_addr, m1_addr,
              algo, algo_key, icv_len, ipsec_mode,
              m2_addr, m1_addr))

    m2.run("ip xfrm policy add src %s dst %s dir out tmpl "\
           "src %s dst %s proto esp mode %s action allow"\
           % (m2_addr, m1_addr,
              m2_addr, m1_addr, ipsec_mode))



for algo, key_len, icv_len in algorithm:
    # test: TCP netperf, UDP netperf
    if ipv in [ 'ipv4', 'both']:
        configure_ipsec(algo,
                        generate_key(key_len),
                        icv_len,
                        "ipv4")

        dump = m1.run("tcpdump -i %s -nn -vv" % m1_if_name, bg=True)

        # ping + PacketAssert
        assert_mod = ctl.get_module("PacketAssert",
                                 options={
                                     "interface": m2_if_name,
                                     "filter": "esp",
                                     "grep_for": [ "ESP\(spi=0x00001001" ],
                                     "min": 10
                                 })

        assert_proc = m2.run(assert_mod, bg=True)

        ping_mod = ctl.get_module("IcmpPing",
                                options={
                                    "addr": m2_if_addr,
                                    "count": 10,
                                    "interval": 0.1})

        ctl.wait(2)

        m1.run(ping_mod)

        ctl.wait(2)

        assert_proc.intr()

        dump.intr()

        # prepare PerfRepo result for tcp
        result_tcp = perf_api.new_result("tcp_ipv4_id",
                                         "tcp_ipv4_result",
                                         hash_ignore=[
                                             r'kernel_release',
                                             r'redhat_release'])
        result_tcp.add_tag(product_name)

        if nperf_num_parallel > 1:
            result_tcp.add_tag("multithreaded")
            result_tcp.set_parameter('num_parallel', nperf_num_parallel)

        result_tcp.set_parameter('ipsec_algorithm', algo)
        result_tcp.set_parameter('key_length', key_len)
        result_tcp.set_parameter('iv_length', icv_len)
        result_tcp.set_parameter('msg_size', nperf_msg_size)
        result_tcp.set_parameter('ipsec_mode', ipsec_mode)

        baseline = perf_api.get_baseline_of_result(result_tcp)
        baseline = perfrepo_baseline_to_dict(baseline)


        tcp_res_data = netperf((m1, m1_if, 0, {"scope": 0}),
                               (m2, m2_if, 0, {"scope": 0}),
                               client_opts={"duration" : netperf_duration,
                                           "testname" : "TCP_STREAM",
                                           "confidence" : nperf_confidence,
                                           "num_parallel" : nperf_num_parallel,
                                           "cpu_util" : nperf_cpu_util,
                                           "runs": nperf_max_runs,
                                           "debug": nperf_debug,
                                           "max_deviation": nperf_max_dev,
                                           "msg_size" : nperf_msg_size,
                                           "netperf_opts": nperf_opts},
                              baseline = baseline,
                              timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

        netperf_result_template(result_tcp, tcp_res_data)
        result_tcp.set_comment(pr_comment)
        perf_api.save_result(result_tcp, official_result)

        # prepare PerfRepo result for udp
        result_udp = perf_api.new_result("udp_ipv4_id",
                                         "udp_ipv4_result",
                                         hash_ignore=[
                                             r'kernel_release',
                                             r'redhat_release'])
        result_udp.add_tag(product_name)

        if nperf_num_parallel > 1:
            result_udp.add_tag("multithreaded")
            result_udp.set_parameter('num_parallel', nperf_num_parallel)

        result_udp.set_parameter('ipsec_algorithm', algo)
        result_udp.set_parameter('key_length', key_len)
        result_udp.set_parameter('iv_length', icv_len)
        result_udp.set_parameter('msg_size', nperf_msg_size)
        result_udp.set_parameter('ipsec_mode', ipsec_mode)

        baseline = perf_api.get_baseline_of_result(result_udp)
        baseline = perfrepo_baseline_to_dict(baseline)

        udp_res_data = netperf((m1, m1_if, 0, {"scope": 0}),
                               (m2, m2_if, 0, {"scope": 0}),
                               client_opts={"duration" : netperf_duration,
                                            "testname" : "UDP_STREAM",
                                            "confidence" : nperf_confidence,
                                            "num_parallel" : nperf_num_parallel,
                                            "cpu_util" : nperf_cpu_util,
                                            "runs": nperf_max_runs,
                                            "debug": nperf_debug,
                                            "max_deviation": nperf_max_dev,
                                            "msg_size" : nperf_msg_size,
                                            "netperf_opts": nperf_opts},
                               baseline = baseline,
                               timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

        netperf_result_template(result_udp, udp_res_data)
        result_udp.set_comment(pr_comment)
        perf_api.save_result(result_udp, official_result)

    if ipv in [ 'ipv6', 'both']:
        configure_ipsec(algo,
                        generate_key(key_len),
                        icv_len,
                        "ipv6")

        dump = m1.run("tcpdump -i %s -nn -vv" % m1_if_name, bg=True)

        # ping + PacketAssert
        assert_mod = ctl.get_module("PacketAssert",
                                 options={
                                     "interface": m2_if_name,
                                     "filter": "esp",
                                     "grep_for": [ "ESP\(spi=0x00001001" ],
                                     "min": 10
                                 })

        assert_proc = m2.run(assert_mod, bg=True)

        ping_mod = ctl.get_module("Icmp6Ping",
                                options={
                                    "addr": m2_if_addr6,
                                    "count": 10,
                                    "interval": 0.1})

        ctl.wait(2)

        m1.run(ping_mod)

        ctl.wait(2)

        assert_proc.intr()

        dump.intr()

        # prepare PerfRepo result for tcp
        result_tcp = perf_api.new_result("tcp_ipv6_id",
                                         "tcp_ipv6_result",
                                         hash_ignore=[
                                             r'kernel_release',
                                             r'redhat_release'])
        result_tcp.add_tag(product_name)

        if nperf_num_parallel > 1:
            result_tcp.add_tag("multithreaded")
            result_tcp.set_parameter('num_parallel', nperf_num_parallel)

        result_tcp.set_parameter('ipsec_algorithm', algo)
        result_tcp.set_parameter('key_length', key_len)
        result_tcp.set_parameter('iv_length', icv_len)
        result_tcp.set_parameter('msg_size', nperf_msg_size)
        result_tcp.set_parameter('ipsec_mode', ipsec_mode)

        baseline = perf_api.get_baseline_of_result(result_tcp)
        baseline = perfrepo_baseline_to_dict(baseline)


        tcp_res_data = netperf((m1, m1_if, 1, {"scope": 0}),
                               (m2, m2_if, 1, {"scope": 0}),
                               client_opts={"duration" : netperf_duration,
                                            "testname" : "TCP_STREAM",
                                            "confidence" : nperf_confidence,
                                            "num_parallel" : nperf_num_parallel,
                                            "cpu_util" : nperf_cpu_util,
                                            "runs": nperf_max_runs,
                                            "debug": nperf_debug,
                                            "max_deviation": nperf_max_dev,
                                            "msg_size" : nperf_msg_size,
                                            "netperf_opts" : nperf_opts + " -6"},
                               baseline = baseline,
                               timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

        netperf_result_template(result_tcp, tcp_res_data)
        result_tcp.set_comment(pr_comment)
        perf_api.save_result(result_tcp, official_result)

        # prepare PerfRepo result for udp
        result_udp = perf_api.new_result("udp_ipv6_id",
                                         "udp_ipv6_result",
                                         hash_ignore=[
                                             r'kernel_release',
                                             r'redhat_release'])
        result_udp.add_tag(product_name)

        if nperf_num_parallel > 1:
            result_udp.add_tag("multithreaded")
            result_udp.set_parameter('num_parallel', nperf_num_parallel)

        result_udp.set_parameter('ipsec_algorithm', algo)
        result_udp.set_parameter('key_length', key_len)
        result_udp.set_parameter('iv_length', icv_len)
        result_udp.set_parameter('msg_size', nperf_msg_size)
        result_udp.set_parameter('ipsec_mode', ipsec_mode)

        baseline = perf_api.get_baseline_of_result(result_udp)
        baseline = perfrepo_baseline_to_dict(baseline)

        udp_res_data = netperf((m1, m1_if, 1, {"scope": 0}),
                               (m2, m2_if, 1, {"scope": 0}),
                               client_opts={"duration" : netperf_duration,
                                            "testname" : "UDP_STREAM",
                                            "confidence" : nperf_confidence,
                                            "num_parallel" : nperf_num_parallel,
                                            "cpu_util" : nperf_cpu_util,
                                            "runs": nperf_max_runs,
                                            "debug": nperf_debug,
                                            "max_deviation": nperf_max_dev,
                                            "msg_size" : nperf_msg_size,
                                            "netperf_opts" : nperf_opts + " -6"},
                               baseline = baseline,
                               timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

        netperf_result_template(result_udp, udp_res_data)
        result_udp.set_comment(pr_comment)
        perf_api.save_result(result_udp, official_result)

m1.run("ip xfrm policy flush")
m1.run("ip xfrm state flush")
m2.run("ip xfrm policy flush")
m2.run("ip xfrm state flush")

if nperf_cpupin:
    m1.run("service irqbalance start")
    m2.run("service irqbalance start")
