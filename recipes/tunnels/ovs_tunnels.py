from lnst.Controller.Task import ctl

from lnst.RecipeCommon.ModuleWrap import netperf
from lnst.RecipeCommon.IRQ import pin_dev_irqs

def run_netperf(netperf_servers, netperf_clients, testname):
    netperf_cli_procs = []
    netperf_srv_procs = []

    timeout = (netperf_duration + nperf_reserve) * nperf_max_runs

    for i in range(0, TUNNEL_COUNT):
        netperf_clients[i].update_options({"testname" : testname})

        netperf_srv_procs.append(h2.run(netperf_servers[i], bg=True, timeout=timeout))
        netperf_cli_procs.append(h1.run(netperf_clients[i], bg=True, timeout=timeout))

    for i in range(0, TUNNEL_COUNT):
        netperf_cli_procs[i].wait()
        netperf_srv_procs[i].intr()

    sum = 0

    for i in range(0, TUNNEL_COUNT):
        sum += netperf_cli_procs[i].get_result()['res_data']['rate']

    res = ctl.get_module("Custom",
                          options={
                              "rate" : sum,
                              "unit" : "bps",
                              "testname" : testname
                              })

    return res

# ------
# SETUP
# ------

# test hosts
h1 = ctl.get_host("test_host1")
h2 = ctl.get_host("test_host2")

for h in [h1, h2]:
    h.sync_resources(modules=["Netperf", "Custom"])

TUNNEL_COUNT = 16

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
nperf_protocols = ctl.get_alias("nperf_protocols")

devices = []

h1_nic = h1.get_interface("if1")
h2_nic = h2.get_interface("if1")

for i in range(0, TUNNEL_COUNT):
    d1 = h1.get_device("int" + str(i))
    d2 = h2.get_device("int" + str(i))
    devices.append((d1, d2))

for h1_dev, h2_dev in devices:
    h1_dev.set_mtu(mtu)
    h2_dev.set_mtu(mtu)

nperf_opts = ""
if nperf_cpupin:
    h1.run("service irqbalance stop")
    h2.run("service irqbalance stop")

    # this will pin devices irqs to cpu #0
    for m, d in [(h1, h1_nic), (h2, h2_nic)]:
        pin_dev_irqs(m, d, 0)

if nperf_cpupin and nperf_num_parallel == 1:
    nperf_opts = " -T%s,%s" % (nperf_cpupin, nperf_cpupin)


ctl.wait(15)

netperf_clients = []
netperf_servers = []
netperf_clients6 = []
netperf_servers6 = []


for h1_dev, h2_dev in devices:
    netperf_clients.append(ctl.get_module("Netperf",
                                      options={
                                          "role" : "client",
                                          "netperf_server": h2_dev.get_ip(0),
                                          "bind": h1_dev.get_ip(0),
                                          "duration" : netperf_duration,
                                          "testname" : "TCP_STREAM",
                                          "confidence" : nperf_confidence,
                                          "cpu_util" : nperf_cpu_util,
                                          "runs": nperf_max_runs,
                                          "debug" : nperf_debug,
                                          "num_parallel" : nperf_num_parallel,
                                          "max_deviation" : nperf_max_dev}))

    netperf_clients6.append(ctl.get_module("Netperf",
                                      options={
                                          "role" : "client",
                                          "netperf_server": h2_dev.get_ip(1),
                                          "bind": h1_dev.get_ip(1),
                                          "duration" : netperf_duration,
                                          "testname" : "TCP_STREAM",
                                          "confidence" : nperf_confidence,
                                          "cpu_util" : nperf_cpu_util,
                                          "runs": nperf_max_runs,
                                          "debug" : nperf_debug,
                                          "num_parallel" : nperf_num_parallel,
                                          "max_deviation" : nperf_max_dev}))

    netperf_servers.append(ctl.get_module("Netperf",
                                      options={
                                          "role" : "server",
                                          "bind": h2_dev.get_ip(0)}))

    netperf_servers6.append(ctl.get_module("Netperf",
                                      options={
                                          "role" : "server",
                                          "bind": h2_dev.get_ip(1)}))


for action in ["on", "off"]:
    h1.run("ethtool -K %s tx-udp_tnl-segmentation %s" % (h1_nic.get_devname(), action))
    h2.run("ethtool -K %s tx-udp_tnl-segmentation %s" % (h2_nic.get_devname(), action))

    #netperfs
    ctl.wait(5)

    if ipv in ["ipv4", "both"]:
        if nperf_protocols.find("tcp") > -1:
            testname = "TCP_STREAM"
            res = run_netperf(netperf_servers, netperf_clients, testname)
            h1.run(res)
        if nperf_protocols.find("udp") > -1:
            testname = "UDP_STREAM"
            res = run_netperf(netperf_servers, netperf_clients, testname)
            h1.run(res)
    if ipv in ["ipv6", "both"]:
        if nperf_protocols.find("tcp") > -1:
            testname = "TCP_STREAM"
            res = run_netperf(netperf_servers6, netperf_clients6, testname)
            h1.run(res)
        if nperf_protocols.find("udp") > -1:
            testname = "UDP_STREAM"
            res = run_netperf(netperf_servers6, netperf_clients6, testname)
            h1.run(res)

if nperf_cpupin:
    h1.run("service irqbalance start")
    h2.run("service irqbalance start")
