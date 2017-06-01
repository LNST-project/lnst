from lnst.Common.Utils import bool_it
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

m1 = ctl.get_host("machine1")
m2 = ctl.get_host("machine2")

m1.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Netperf"])
m2.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Netperf"])

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
nperf_protocols = ctl.get_alias("nperf_protocols")
official_result = bool_it(ctl.get_alias("official_result"))

pr_comment = generate_perfrepo_comment([m1, m2], pr_user_comment)

m1_phy = m1.get_interface("eth")
m2_phy = m2.get_interface("eth")

m1_phy.set_mtu(mtu)
m2_phy.set_mtu(mtu)

m1_phy_name = m1_phy.get_devname()
m2_phy_name = m2_phy.get_devname()

m1_phy_addr = m1_phy.get_ip()
m2_phy_addr = m2_phy.get_ip()

m1_phy_hwaddr = m1_phy.get_hwaddr()
m2_phy_hwaddr = m2_phy.get_hwaddr()

key1 = "7a16780284000775d4f0a3c0f0e092c0"
key2 = "3212ef5c4cc5d0e4210b17208e88779e"

msec_tif_name = "macsec0"
m1_tif_addr = "192.168.100.1"
m2_tif_addr = "192.168.100.2"

m1_tif_addr6 = "fc00::1"
m2_tif_addr6 = "fc00::2"

#macsec setup
def macsecSetup(encryption):
    m1.run("ip link add link %s %s type macsec encrypt %s" %
            (m1_phy_name, msec_tif_name, encryption))
    m1.run("ip macsec add %s rx port 1 address %s" % (msec_tif_name, m2_phy_hwaddr))
    m1.run("ip macsec add %s tx sa 0 pn 1 on key 00 %s" % (msec_tif_name, key1))
    m1.run("ip macsec add %s rx port 1 address %s sa 0 pn 1 on key 01 %s" %
            (msec_tif_name, m2_phy_hwaddr, key2))

    m2.run("ip link add link %s %s type macsec encrypt %s" %
            (m2_phy_name, msec_tif_name, encryption))
    m2.run("ip macsec add %s rx port 1 address %s" % (msec_tif_name, m1_phy_hwaddr))
    m2.run("ip macsec add %s tx sa 0 pn 1 on key 01 %s" % (msec_tif_name, key2))
    m2.run("ip macsec add %s rx port 1 address %s sa 0 pn 1 on key 00 %s" %
            (msec_tif_name, m1_phy_hwaddr, key1))

    m1.run("ip link set %s up" % msec_tif_name)
    m2.run("ip link set %s up" % msec_tif_name)

    m1.run("ip addr add %s/24 dev %s" % (m1_tif_addr, msec_tif_name))
    m2.run("ip addr add %s/24 dev %s" % (m2_tif_addr, msec_tif_name))

    m1.run("ip -6 addr add %s/64 dev %s" % (m1_tif_addr6, msec_tif_name))
    m2.run("ip -6 addr add %s/64 dev %s" % (m2_tif_addr6, msec_tif_name))


if nperf_cpupin:
    m1.run("service irqbalance stop")
    m2.run("service irqbalance stop")

    dev_list = [(m1, m1_phy), (m2, m2_phy)]

    # this will pin devices irqs to cpu #0
    for m, d in dev_list:
        pin_dev_irqs(m, d, 0)

nperf_opts = ""
if nperf_cpupin and nperf_num_parallel == 1:
    nperf_opts = " -T%s,%s" % (nperf_cpupin, nperf_cpupin)

ctl.wait(15)

ping_opts = {"count": 100, "interval": 0.1}

encryption_settings = ['on', 'off']

#availability check
ping((m1, m1_phy, 0, {"scope": 0}),
     (m2, m2_phy, 0, {"scope": 0}),
     options=ping_opts)

ctl.wait(2)

client_opts = {"duration" : netperf_duration,
               "testname" : "TCP_STREAM",
               "confidence" : nperf_confidence,
               "num_parallel" : nperf_num_parallel,
               "cpu_util" : nperf_cpu_util,
               "runs": nperf_max_runs,
               "netperf_opts": nperf_opts,
               "debug": nperf_debug,
               "max_deviation": nperf_max_dev}

if nperf_msg_size is not None:
    client_opts["msg_size"] = nperf_msg_size

for setting in encryption_settings:
    #macsec setup
    macsecSetup(setting)
    m1_tif = m1.get_device(msec_tif_name)
    m2_tif = m2.get_device(msec_tif_name)

    if ipv in [ 'ipv4', 'both' ]:
        ping((m1, m1_tif, 0, {"scope": 0}),
             (m2, m2_tif, 0, {"scope": 0}),
             options=ping_opts)

        ctl.wait(2)


        if nperf_protocols.find("tcp") > -1:
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

            result_tcp.set_parameter('encryption', setting)

            if nperf_msg_size is not None:
                result_tcp.set_parameter("nperf_msg_size", nperf_msg_size)

            baseline = perf_api.get_baseline_of_result(result_tcp)
            baseline = perfrepo_baseline_to_dict(baseline)

            client_opts["testname"] = "TCP_STREAM"
            client_opts["netperf_opts"] = nperf_opts

            tcp_res_data = netperf((m1, m1_tif, 0, {"scope": 0}),
                                   (m2, m2_tif, 0, {"scope": 0}),
                                   client_opts = client_opts, baseline = baseline,
                                   timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

            netperf_result_template(result_tcp, tcp_res_data)
            result_tcp.set_comment(pr_comment)
            perf_api.save_result(result_tcp, official_result)

        if nperf_protocols.find("udp") > -1:
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

            result_udp.set_parameter('encryption', setting)

            if nperf_msg_size is not None:
                result_udp.set_parameter("nperf_msg_size", nperf_msg_size)

            baseline = perf_api.get_baseline_of_result(result_udp)
            baseline = perfrepo_baseline_to_dict(baseline)

            client_opts["testname"] = "UDP_STREAM"
            client_opts["netperf_opts"] = nperf_opts

            udp_res_data = netperf((m1, m1_tif, 0, {"scope": 0}),
                                   (m2, m2_tif, 0, {"scope": 0}),
                                   client_opts = client_opts, baseline = baseline,
                                   timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

            netperf_result_template(result_udp, udp_res_data)
            result_udp.set_comment(pr_comment)
            perf_api.save_result(result_udp, official_result)


    if ipv in [ 'ipv6', 'both' ]:
        ping6((m1, m1_tif, 1, {"scope": 0}),
              (m2, m2_tif, 1, {"scope": 0}),
              options=ping_opts)

        ctl.wait(2)

        if nperf_protocols.find("tcp") > -1:
            # prepare PerfRepo result for tcp ipv6
            result_tcp = perf_api.new_result("tcp_ipv6_id",
                                             "tcp_ipv6_result",
                                             hash_ignore=[
                                                 r'kernel_release',
                                                 r'redhat_release'])
            result_tcp.add_tag(product_name)
            if nperf_num_parallel > 1:
                result_tcp.add_tag("multithreaded")
                result_tcp.set_parameter('num_parallel', nperf_num_parallel)

            result_tcp.set_parameter('encryption', setting)

            if nperf_msg_size is not None:
                result_tcp.set_parameter("nperf_msg_size", nperf_msg_size)

            baseline = perf_api.get_baseline_of_result(result_tcp)
            baseline = perfrepo_baseline_to_dict(baseline)

            client_opts["testname"] = "TCP_STREAM"
            client_opts["netperf_opts"] = nperf_opts + " -6"

            tcp_res_data = netperf((m1, m1_tif, 1, {"scope": 0}),
                                   (m2, m2_tif, 1, {"scope": 0}),
                                   client_opts = client_opts, baseline = baseline,
                                   timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

            netperf_result_template(result_tcp, tcp_res_data)
            result_tcp.set_comment(pr_comment)
            perf_api.save_result(result_tcp, official_result)

        if nperf_protocols.find("udp") > -1:
            # prepare PerfRepo result for udp ipv6
            result_udp = perf_api.new_result("udp_ipv6_id",
                                             "udp_ipv6_result",
                                             hash_ignore=[
                                                 r'kernel_release',
                                                 r'redhat_release'])
            result_udp.add_tag(product_name)
            if nperf_num_parallel > 1:
                result_udp.add_tag("multithreaded")
                result_udp.set_parameter('num_parallel', nperf_num_parallel)

            result_udp.set_parameter('encryption', setting)

            if nperf_msg_size is not None:
                result_udp.set_parameter("nperf_msg_size", nperf_msg_size)

            baseline = perf_api.get_baseline_of_result(result_udp)
            baseline = perfrepo_baseline_to_dict(baseline)

            client_opts["testname"] = "UDP_STREAM"
            client_opts["netperf_opts"] = nperf_opts + " -6"

            udp_res_data = netperf((m1, m1_tif, 1, {"scope": 0}),
                                   (m2, m2_tif, 1, {"scope": 0}),
                                   client_opts = client_opts, baseline = baseline,
                                   timeout = (netperf_duration + nperf_reserve)*nperf_max_runs)

            netperf_result_template(result_udp, udp_res_data)
            result_udp.set_comment(pr_comment)
            perf_api.save_result(result_udp, official_result)


    m1.run("ip link delete %s" % msec_tif_name)
    m2.run("ip link delete %s" % msec_tif_name)

if nperf_cpupin:
    m1.run("service irqbalance start")
    m2.run("service irqbalance start")
