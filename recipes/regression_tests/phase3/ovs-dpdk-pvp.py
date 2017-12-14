import re
import xml.etree.ElementTree as ET
import paramiko
import logging
from tempfile import NamedTemporaryFile
from lnst.Common.Utils import bool_it, std_deviation, dict_to_dot, Noop
from lnst.Controller.Task import ctl
from lnst.Controller.PerfRepoUtils import perfrepo_baseline_to_dict
from lnst.RecipeCommon.ModuleWrap import ping
from lnst.RecipeCommon.PerfRepo import generate_perfrepo_comment

logging.getLogger("paramiko.transport").setLevel(logging.ERROR)

def run_ssh_command_on_guest(command, guest, host, guest_name=""):
    stdin, stdout, stderr = guest.exec_command(command)
    if stdout.channel.recv_exit_status() > 0:
        custom_mod = ctl.get_module("Custom", options = {"fail": True})
    else:
        custom_mod = ctl.get_module("Custom")
    desc = "%s: %s" % (guest_name, command)
    host.run(custom_mod, desc=desc)
    stdout = "".join(stdout)
    return stdout

def run_ssh_command_on_bg_channel(command, channel, host, guest_name=""):
    channel.exec_command(command)
    custom_mod = ctl.get_module("Custom")
    desc = "%s running in bg: %s" % (guest_name, command)
    host.run(custom_mod, desc=desc)

def compare_results(host, result, baseline, max_dev):
    avg1 = result.get_value("rx_rate").get_result()
    dev1 = result.get_value("rx_rate_deviation").get_result()
    interval1 = (avg1 - dev1, avg1 + dev1)

    avg2 = baseline.get_value("rx_rate").get_result()
    dev2 = baseline.get_value("rx_rate_deviation").get_result()
    interval2 = (avg2 - dev2, avg2 + dev2)

    if interval1[1] < interval2[0]:
        desc = ("Measured rate {:.2f} +-{:.2f} pps is lower "
                "than threshold {:.2f} +-{:.2f} pps".
                format(avg1, dev1, avg2, dev2))
        custom_mod = ctl.get_module("Custom", options = {"fail": True})
    else:
        desc = ("Measured rate {:.2f} +-{:.2f} pps is higher "
                "than threshold {:.2f} +-{:.2f} pps".
                format(avg1, dev1, avg2, dev2))
        custom_mod = ctl.get_module("Custom")

    host.run(custom_mod, desc=desc)

def report_result(host, result, max_dev):
    avg = result.get_value("rx_rate").get_result()
    dev = result.get_value("rx_rate_deviation").get_result()

    desc = "Measured rate is {:.2f} +-{:.2f} pps".format(avg, dev)
    fail = False
    if re.match("\d+%", max_dev):
        if ((float(dev) / avg) * 100)  > int(max_dev[:-1]):
            desc = ("Measured rate {:.2f} +-{:.2f} pps has bigger "
                    "deviation than allowed (+-{})".
                    format(avg, dev, max_dev))
            fail = True
    elif re.match("\d+", max_dev):
        if dev > int(max_dev):
            desc = ("Measured rate {:.2f} +-{:.2f} pps has bigger "
                    "deviation than allowed (+-{} pps)".
                    format(avg, dev, max_dev))
            fail = True
    elif max_dev == None:
        pass
    else:
        raise Exception("Unsupported format for max_dev argument.")

    custom_mod = ctl.get_module("Custom", options={"fail": fail})
    host.run(custom_mod, desc=desc)

# ------
# SETUP
# ------

mapping_file = ctl.get_alias("mapping_file")
perf_api = ctl.connect_PerfRepo(mapping_file)

product_name = ctl.get_alias("product_name")

# test hosts
h1 = ctl.get_host("host1")
h2 = ctl.get_host("host2")

h1.sync_resources(modules=["IcmpPing", "TRexClient", "TRexServer", "Custom"])
h2.sync_resources(modules=["IcmpPing", "Custom"])

dpdk_version = h1.run("testpmd -v --help 2>&1").get_result()["res_data"]["stdout"]
tmp = re.search(r"^.*RTE Version: '(.*)'$", dpdk_version, flags=re.MULTILINE)
if tmp:
    dpdk_version = tmp.group(1)
else:
    dpdk_version = "unknown"

# ------
# TESTS
# ------

official_result = bool_it(ctl.get_alias("official_result"))
pr_user_comment = ctl.get_alias("perfrepo_comment")
host1_dpdk_cores = ctl.get_alias("host1_dpdk_cores")
host2_dpdk_cores = ctl.get_alias("host2_dpdk_cores")
guest_dpdk_cores = ctl.get_alias("guest_dpdk_cores")
nr_hugepages = int(ctl.get_alias("nr_hugepages"))
socket_mem = int(ctl.get_alias("socket_mem"))
guest_mem_amount = ctl.get_alias("guest_mem_amount")
guest_virtname = ctl.get_alias("guest_virtname")
guest_hostname = ctl.get_alias("guest_hostname")
guest_username = ctl.get_alias("guest_username")
guest_password = ctl.get_alias("guest_password")
guest_cpus = ctl.get_alias("guest_cpus")
trex_dir = ctl.get_alias("trex_dir")
pkt_size = int(ctl.get_alias("pkt_size"))
test_duration = int(ctl.get_alias("test_duration"))
test_runs = int(ctl.get_alias("test_runs"))
max_dev = ctl.get_alias("max_dev")

pr_comment = generate_perfrepo_comment([h1, h2], pr_user_comment)
pr_comment += "\n<BR>DPDK version: {}".format(dpdk_version)

h1_nic1 = h1.get_interface("if1")
h1_nic2 = h1.get_interface("if2")
h2_nic1 = h2.get_interface("if1")
h2_nic2 = h2.get_interface("if2")


#============================================
# WARMP UP - teach switch about mac addresses
#============================================

h1_nic1.set_addresses(["192.168.1.1/24"])
h1_nic2.set_addresses(["192.168.1.3/24"])

h2_nic1.set_addresses(["192.168.1.2/24"])
h2_nic2.set_addresses(["192.168.1.4/24"])

ctl.wait(5)

ping_opts = {"count": 100, "interval": 0.1, "limit_rate": 20}

pings = []
pings.append(ping((h1, h1_nic1, 0, {"scope": 0}),
                  (h2, h2_nic1, 0, {"scope": 0}),
                  options=ping_opts, bg=True))
pings.append(ping((h1, h1_nic2, 0, {"scope": 0}),
                  (h2, h2_nic2, 0, {"scope": 0}),
                  options=ping_opts, bg=True))

pings.append(ping((h2, h2_nic1, 0, {"scope": 0}),
                  (h1, h1_nic1, 0, {"scope": 0}),
                  options=ping_opts, bg=True))
pings.append(ping((h2, h2_nic2, 0, {"scope": 0}),
                  (h1, h1_nic2, 0, {"scope": 0}),
                  options=ping_opts, bg=True))

for i in pings:
    i.wait()

#============================================
# WARMP UP END
#============================================


h1.run("service irqbalance stop")
h2.run("service irqbalance stop")
# this will pin all irqs to cpu #0
h1.run("MASK=1; for i in `ls -d /proc/irq/[0-9]*` ; do echo $MASK > ${i}/smp_affinity ; done")
h2.run("MASK=1; for i in `ls -d /proc/irq/[0-9]*` ; do echo $MASK > ${i}/smp_affinity ; done")

#============================================
# configure hugepages
#============================================

h1.config("/sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages", nr_hugepages)
h2.config("/sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages", nr_hugepages)

#============================================
# Host2 configure openvswitch to use DPDK
#============================================

h2.enable_service("openvswitch")
h2.run("ovs-vsctl --no-wait set Open_vSwitch . other_config:dpdk-init=true")
h2.run("ovs-vsctl --no-wait set Open_vSwitch . other_config:dpdk-socket-mem=%d" % socket_mem)
h2.run("ovs-vsctl --no-wait set Open_vSwitch . other_config:pmd-cpu-mask=%s" % host2_dpdk_cores)
h2.restart_service("openvswitch")

#============================================
# Host1 bind NICs to vfio-pci
#============================================

h1_nic1_out = h1.run("ethtool -i %s" % h1_nic1.get_devname()).get_result()["res_data"]["stdout"]
h1_nic2_out = h1.run("ethtool -i %s" % h1_nic2.get_devname()).get_result()["res_data"]["stdout"]

h1_nic1_pci = re.search("^bus-info: (\S+)$", h1_nic1_out, re.MULTILINE).group(1)
h1_nic2_pci = re.search("^bus-info: (\S+)$", h1_nic2_out, re.MULTILINE).group(1)

h1.run("modprobe vfio-pci")
h1.run("driverctl set-override %s vfio-pci" % h1_nic1_pci)
h1.run("driverctl set-override %s vfio-pci" % h1_nic2_pci)

#============================================
# Host2 bind NICs to vfio-pci
#============================================

h2_nic1_out = h2.run("ethtool -i %s" % h2_nic1.get_devname()).get_result()["res_data"]["stdout"]
h2_nic2_out = h2.run("ethtool -i %s" % h2_nic2.get_devname()).get_result()["res_data"]["stdout"]

h2_nic1_pci = re.search("^bus-info: (\S+)$", h2_nic1_out, re.MULTILINE).group(1)
h2_nic2_pci = re.search("^bus-info: (\S+)$", h2_nic2_out, re.MULTILINE).group(1)

h2.run("modprobe vfio-pci")
h2.run("driverctl set-override %s vfio-pci" % h2_nic1_pci)
h2.run("driverctl set-override %s vfio-pci" % h2_nic2_pci)

#============================================
# Host2 add DPDK NICs as openvswitch ports
#============================================

h2.restart_service("openvswitch")

h2.run("ovs-vsctl add-br br0 -- set bridge br0 datapath_type=netdev")
h2.run("ovs-vsctl add-port br0 nic1 -- set interface nic1 type=dpdk ofport_request=11 options:dpdk-devargs=%s" % h2_nic1_pci)
h2.run("ovs-vsctl add-port br0 nic2 -- set interface nic2 type=dpdk ofport_request=12 options:dpdk-devargs=%s" % h2_nic2_pci)

#============================================
# Host2 configure Guest with vhostuser NICs
#============================================

h2.run("virsh destroy %s || true" % guest_virtname)
dumpxml = h2.run("virsh dumpxml %s" % guest_virtname)
dumpxml_out = dumpxml.get_result()["res_data"]["stdout"]
guest_xml = ET.fromstring(dumpxml_out)

original_guest_xml = NamedTemporaryFile("w+b", delete=False)
original_guest_xml.write(dumpxml_out)
original_guest_xml.close()
original_guest_xml_path = h2.copy_file_to_machine(original_guest_xml.name)

devices = guest_xml.find("devices")

interface1 = ET.SubElement(devices, 'interface', type='vhostuser')
ET.SubElement(interface1, 'mac', address=str(h2_nic1.get_hwaddr()))
ET.SubElement(interface1, 'model', type='virtio')
ET.SubElement(interface1, 'source', type='unix', path='/tmp/vhost_nic1', mode='server')

interface2 = ET.SubElement(devices, 'interface', type='vhostuser')
ET.SubElement(interface2, 'mac', address=str(h2_nic2.get_hwaddr()))
ET.SubElement(interface2, 'model', type='virtio')
ET.SubElement(interface2, 'source', type='unix', path='/tmp/vhost_nic2', mode='server')

#============================================
# Host2 add vhostuser ports to the openvswitch bridge
#============================================
h2.run("ovs-vsctl add-port br0 guest_nic1 -- set interface guest_nic1 type=dpdkvhostuserclient ofport_request=21 options:vhost-server-path=/tmp/vhost_nic1")

h2.run("ovs-vsctl add-port br0 guest_nic2 -- set interface guest_nic2 type=dpdkvhostuserclient ofport_request=22 options:vhost-server-path=/tmp/vhost_nic2")

#============================================
# Host2 configure Numa memory access
#============================================

cpu = guest_xml.find("cpu")
numa = ET.SubElement(cpu, 'numa')
ET.SubElement(numa, 'cell', id='0', cpus='0', memory=guest_mem_amount, unit='KiB', memAccess='shared')

cputune = ET.SubElement(guest_xml, "cputune")
for i, cpu_id in enumerate(guest_cpus.split(',')):
    ET.SubElement(cputune, "vcpupin", vcpu=str(i), cpuset=str(cpu_id))

updated_guest_xml = NamedTemporaryFile("w+b", delete=False)
updated_guest_xml.write(ET.tostring(guest_xml))
updated_guest_xml.close()
updated_guest_xml_path = h2.copy_file_to_machine(updated_guest_xml.name)

h2.run("virsh define %s" % updated_guest_xml_path)
h2.run("virsh start %s" % guest_virtname)

#============================================
# Host2 wait for guest start
#============================================
ctl.wait(60)

#============================================
# Host2 add openvswitch flows between DPDK NICs and Guest NICs
#============================================

h2.run("ovs-ofctl del-flows br0")
h2.run("ovs-ofctl add-flow br0 in_port=11,action=21")
h2.run("ovs-ofctl add-flow br0 in_port=21,action=11")
h2.run("ovs-ofctl add-flow br0 in_port=12,action=22")
h2.run("ovs-ofctl add-flow br0 in_port=22,action=12")

#============================================
# Guest configure DPDK for vhostuser nics
#============================================

guest = paramiko.SSHClient()
guest.set_missing_host_key_policy(paramiko.AutoAddPolicy())
guest.connect(guest_hostname, username=guest_username, password=guest_password)

run_ssh_command_on_guest("service irqbalance stop", guest, h2, guest_virtname)
run_ssh_command_on_guest("MASK=1; for i in `ls -d /proc/irq/[0-9]*` ; do echo $MASK > ${i}/smp_affinity ; done", guest, h2, guest_virtname)

g_nic1_search = run_ssh_command_on_guest("grep -i %s /sys/class/net/*/address" % str(h2_nic1.get_hwaddr()), guest, h2, guest_virtname)
g_nic1_name = re.search("/sys/class/net/(.*)/address", g_nic1_search).group(1)

g_nic2_search = run_ssh_command_on_guest("grep -i %s /sys/class/net/*/address" % str(h2_nic2.get_hwaddr()), guest, h2, guest_virtname)
g_nic2_name = re.search("/sys/class/net/(.*)/address", g_nic2_search).group(1)

g_nic1_out = run_ssh_command_on_guest("ethtool -i %s" % g_nic1_name, guest, h2, guest_virtname)
g_nic2_out = run_ssh_command_on_guest("ethtool -i %s" % g_nic2_name, guest, h2, guest_virtname)

g_nic1_pci = re.search("^bus-info: (\S+)$", g_nic1_out, re.MULTILINE).group(1)
g_nic2_pci = re.search("^bus-info: (\S+)$", g_nic2_out, re.MULTILINE).group(1)

run_ssh_command_on_guest("echo -n %d >/sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages" % nr_hugepages, guest, h2, guest_virtname)
run_ssh_command_on_guest("modprobe -r vfio_iommu_type1", guest, h2, guest_virtname)
run_ssh_command_on_guest("modprobe -r vfio", guest, h2, guest_virtname)
run_ssh_command_on_guest("modprobe vfio enable_unsafe_noiommu_mode=1", guest, h2, guest_virtname)
run_ssh_command_on_guest("modprobe vfio-pci", guest, h2, guest_virtname)
run_ssh_command_on_guest("driverctl set-override %s vfio-pci" % g_nic1_pci, guest, h2, guest_virtname)
run_ssh_command_on_guest("driverctl set-override %s vfio-pci" % g_nic2_pci, guest, h2, guest_virtname)


testpmd_shell = guest.get_transport().open_session()

testpmd_cmd = ("testpmd -c {coremask} "
                      "-w {pci1} -w {pci2} "
                      "-n 4 --socket-mem 1024,0 -- "
                      "-i --eth-peer=0,{hw1} --eth-peer=1,{hw2} "
                      "--forward-mode=mac").format(
                          coremask=guest_dpdk_cores,
                          pci1=g_nic1_pci, pci2=g_nic2_pci,
                          hw1=h1_nic1.get_hwaddr(), hw2=h1_nic2.get_hwaddr())

#============================================
# ovs-dpdk configuration descriptions
#============================================
host_conf = {"host1": {"trex_interfaces": [h1_nic1.get_hwaddr(),
                                           h1_nic2.get_hwaddr()]},
             "host2": {"ovs_bridge": {"name": "br0",
                                      "ports": [("nic1", h2_nic1.get_hwaddr()),
                                                ("nic2", h2_nic2.get_hwaddr()),
                                                ("guest_nic1", h2_nic1.get_hwaddr()),
                                                ("guest_nic2", h2_nic2.get_hwaddr())],
                                      "flows": ["nic1 -> guest_nic1",
                                                "guest_nic1 -> nic1",
                                                "nic2 -> guest_nic2",
                                                "guest_nic1 -> nic2"]}},
             "guest": {"dpdk_interfaces": [h2_nic1.get_hwaddr(),
                                           h2_nic2.get_hwaddr()],
                       "testpmd": {"forward-mode": "mac"}}}

trex_client_conf = {"duration": test_duration,
        "pkt_size": pkt_size,
        "runs": test_runs,
        "trex_path": trex_dir,
        "ports": [0, 1],
        "port0_src_mac": str(h1_nic1.get_hwaddr()),
        "port0_dst_mac": str(h2_nic1.get_hwaddr()),
        "port1_src_mac": str(h1_nic2.get_hwaddr()),
        "port1_dst_mac": str(h2_nic2.get_hwaddr())}

short_h1_nic1_pci = h1_nic1_pci[h1_nic1_pci.find(':')+1:]
short_h1_nic2_pci = h1_nic2_pci[h1_nic2_pci.find(':')+1:]
trex_server_conf = {'port_limit': 2,
                    'version': 2,
                    'interfaces': [short_h1_nic1_pci, short_h1_nic2_pci],
                    'platform': {'dual_if': [{'socket': 0,
                                              'threads': host1_dpdk_cores.split(',')}],
                                 'latency_thread_id': 0,
                                 'master_thread_id': 1},
                    'port_info': [{'dest_mac': str(h2_nic1.get_hwaddr()),
                                   'src_mac': str(h1_nic1.get_hwaddr())},
                                  {'dest_mac': str(h2_nic2.get_hwaddr()),
                                   'src_mac': str(h1_nic2.get_hwaddr())}]}

#============================================
# overall configuration for PerfRepo TestExecution objects
#============================================
ovs_dpdk_conf = {"hosts_conf": host_conf,
                 "test_conf": {"duration": test_duration,
                               "runs": test_runs,
                               "pkt_size": pkt_size}}

#============================================
# Guest start testpmd for the DPDK vhostuser NICs
#============================================

run_ssh_command_on_guest("mkfifo /tmp/testpmd_stdio", guest, h2, guest_virtname)
run_ssh_command_on_bg_channel("tail -f /tmp/testpmd_stdio | {}".format(testpmd_cmd),
        testpmd_shell, h2, guest_virtname)

run_ssh_command_on_guest("echo \"start tx_first\" > /tmp/testpmd_stdio", guest, h2, guest_virtname)

trex_client_mod = ctl.get_module("TRexClient",
        options=trex_client_conf)

trex_server_mod = ctl.get_module("TRexServer",
        options={"trex_path": trex_dir,
                 "trex_config": [trex_server_conf]})

trex_server = h1.run(trex_server_mod, bg=True)

#wait for the server to start
ctl.wait(5)

results = h1.run(trex_client_mod, timeout=(test_duration+10)*test_runs)
trex_result = results.get_result()

trex_server.intr()

#============================================
# Aggregate result
#============================================

port0_rates = [i["port_0"]["rx_pps"] for i in trex_result["res_data"]["results"]]
port1_rates = [i["port_1"]["rx_pps"] for i in trex_result["res_data"]["results"]]
aggregate_rates = map(sum, zip(port0_rates, port1_rates))

aggr_std_dev = std_deviation(aggregate_rates)

avg_rate = sum(aggregate_rates)/len(aggregate_rates)
avg_rate_port0 = sum(port0_rates)/len(port0_rates)
avg_rate_port1 = sum(port1_rates)/len(port1_rates)
rate_deviation = 2*aggr_std_dev

# prepare PerfRepo result for tcp
pr_result = perf_api.new_result("ovs_dpdk_pvp_2streams_id",
                                "ovs_dpdk_pvp_2streams",
                                 hash_ignore=[r'kernel_release',
                                              r'redhat_release',
                                              r'trex_path',
                                              r'dpdk_version',
                                              r'test_conf.duration',
                                              r'test_conf.runs'])
pr_result.set_configuration(ovs_dpdk_conf)
pr_result.add_tag(product_name)
pr_result.set_parameter("dpdk_version", dpdk_version)

#netperf_result_template(result_tcp, tcp_res_data)
pr_result.add_value('rx_rate', avg_rate)
pr_result.add_value('rx_rate_min', avg_rate - rate_deviation)
pr_result.add_value('rx_rate_max', avg_rate + rate_deviation)
pr_result.add_value('rx_rate_deviation', rate_deviation)

pr_result.add_value('port0_rate', avg_rate_port0)
pr_result.add_value('port1_rate', avg_rate_port1)

baseline = perf_api.get_baseline_of_result(pr_result)
pr_result.set_comment(pr_comment)
perf_api.save_result(pr_result, official_result)

report_result(h1, pr_result.get_testExecution(), max_dev)
if not isinstance(baseline, Noop):
    compare_results(h1, pr_result.get_testExecution(), baseline.get_texec(), max_dev)

#============================================
# Configuration cleanup
#============================================

run_ssh_command_on_guest("echo \"stop\" > /tmp/testpmd_stdio", guest, h2, guest_virtname)
run_ssh_command_on_guest("echo \"quit\" > /tmp/testpmd_stdio", guest, h2, guest_virtname)
run_ssh_command_on_guest("rm -rf /tmp/testpmd_stdio", guest, h2, guest_virtname)

run_ssh_command_on_guest("driverctl unset-override %s" % g_nic1_pci, guest, h2, guest_virtname)
run_ssh_command_on_guest("driverctl unset-override %s" % g_nic2_pci, guest, h2, guest_virtname)

run_ssh_command_on_guest("service irqbalance start", guest, h2, guest_virtname)

guest.close()

h2.run("ovs-ofctl del-flows br0")
h2.run("ovs-vsctl del-port br0 guest_nic2")
h2.run("ovs-vsctl del-port br0 guest_nic1")
h2.run("ovs-vsctl del-port br0 nic1")
h2.run("ovs-vsctl del-port br0 nic2")
h2.run("ovs-vsctl del-br br0")

h2.run("virsh shutdown %s || true" % guest_virtname)

#required to free up the bus so that we can return the devices to the original
#driver should be possible to remove this for OVS version >= 2.8 TODO
h2.restart_service("openvswitch")
h2.run("driverctl unset-override %s & sleep 1; systemctl restart openvswitch" % h2_nic1_pci)
h2.run("driverctl unset-override %s & sleep 1; systemctl restart openvswitch" % h2_nic2_pci)

h2.run("virsh define %s" % original_guest_xml_path)

h1.run("driverctl unset-override %s &" % h1_nic1_pci)
h1.run("driverctl unset-override %s &" % h1_nic2_pci)

h1.run("service irqbalance start")
h2.run("service irqbalance start")
