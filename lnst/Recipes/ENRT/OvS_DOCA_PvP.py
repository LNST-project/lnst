import logging
import re
import signal
import time
import xml.etree.ElementTree as ET

from lnst.Common.IpAddress import interface_addresses
from lnst.Common.LnstError import LnstError
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.Parameters import (
    BoolParam,
    IntParam,
    IPv4NetworkParam,
    Param,
    StrParam,
)
from lnst.Controller.RecipeResults import ResultLevel, ResultType
from lnst.RecipeCommon.Perf.Measurements import Flow as PerfFlow
from lnst.RecipeCommon.Perf.Measurements import StatCPUMeasurement, TRexFlowMeasurement
from lnst.RecipeCommon.Perf.Recipe import RecipeConf as PerfRecipeConf
from lnst.Recipes.ENRT.BasePvPRecipe import BasePvPRecipe, BasePvPTestConf
from lnst.Recipes.ENRT.RecipeReqs import PvPReq
from lnst.Recipes.ENRT.SRIOVDevices import SRIOVDevices
from lnst.Tests.TestPMD import TestPMD


class HostdevDevice(object):
    def __init__(self, hwaddr, bus_info):
        self.hwaddr = str(hwaddr)
        self.bus_info = str(bus_info)


class OVSDOCAPvPTestConf(BasePvPTestConf):
    class DUTConf(BasePvPTestConf.BaseHostConf):
        def __init__(self):
            super(OVSDOCAPvPTestConf.DUTConf, self).__init__()
            self.trex_path = ""
            self.doca_ports = []
            self.vm_ports = []
            self.sriov_devices = []
            self.vfs = []
            self.vf_reps = []
            self.hostdev_vfs = []
            self.configured_eswitch_devices = {}

    class GuestConf(BasePvPTestConf.BaseGuestConf):
        def __init__(self):
            super(OVSDOCAPvPTestConf.GuestConf, self).__init__()
            self.testpmd = None

    def __init__(self):
        self.generator = self.BaseHostConf()
        self.dut = self.DUTConf()
        self.guest = self.GuestConf()
        self.numa_node = 0


class OvSDOCAPvPRecipe(PvPReq, BasePvPRecipe):
    net_ipv4 = IPv4NetworkParam(default="192.168.1.0/24")

    trex_dir = StrParam(default="/opt/trex")
    guest_name = StrParam(default="guest1")
    guest_cpus = StrParam(default="2,3")
    guest_emulatorpin_cpu = StrParam(default="1")

    guest_dpdk_cores = StrParam(default="0x2")
    guest_testpmd_cores = StrParam(default="0x3")
    guest_driver = StrParam(default="mlx5")

    host1_dpdk_cores = StrParam(default="2,4,6,8,10,12,14,16")

    doca_bridge_name = StrParam(default="br0")
    doca_testpmd_forward_mode = StrParam(default="mac")

    cpu_perf_tool = Param(default=StatCPUMeasurement)

    perf_duration = IntParam(default=60)
    perf_iterations = IntParam(default=5)
    perf_msg_size = IntParam(default=64)
    perf_streams = IntParam(default=1)

    perf_test_simulation = BoolParam(default=False)
    min_offload_ratio = IntParam(default=50)

    def test(self):
        self.check_dependencies()
        config = OVSDOCAPvPTestConf()
        self.pvp_test(config)

    def check_dependencies(self):
        host2 = self.matched.host2
        job = host2.run("ovs-vswitchd --version", job_level=ResultLevel.DEBUG)
        if not job.passed:
            raise LnstError("ovs-vswitchd is not installed on DUT (host2)")

        job = host2.run("devlink -V", job_level=ResultLevel.DEBUG)
        if not job.passed:
            job = host2.run("which devlink", job_level=ResultLevel.DEBUG)
            if not job.passed:
                raise LnstError("devlink utility is not installed on DUT (host2)")

        job = host2.run("virsh --version", job_level=ResultLevel.DEBUG)
        if not job.passed:
            raise LnstError("libvirt / virsh is not available on DUT (host2)")

        for nic in [self.matched.host2.eth0, self.matched.host2.eth1]:
            self.check_sriov_capacity(host2, nic, required_vfs=1)

    def pvp_test(self, config):
        try:
            self.test_wide_configuration(config)

            perf_config = self.generate_perf_config(config)
            result = self.perf_test(perf_config)
            try:
                host2 = config.dut.host
                self._evaluate_dpctl_offload(host2)
                flows_dump = host2.run("ovs-ofctl dump-flows br0", job_level=ResultLevel.DEBUG)
                if flows_dump and flows_dump.stdout:
                    logging.debug(f"OVS OpenFlow dump-flows:\n{flows_dump.stdout}")
                dp_dump = host2.run("ovs-appctl dpctl/dump-flows -m", job_level=ResultLevel.DEBUG)
                if dp_dump and dp_dump.stdout:
                    logging.debug(f"OVS Datapath dump-flows (-m):\n{dp_dump.stdout}")
                dp_offload = host2.run("ovs-appctl dpctl/dump-flows type=offloaded", job_level=ResultLevel.DEBUG)
                if dp_offload and dp_offload.stdout:
                    logging.debug(f"OVS Datapath offloaded flows:\n{dp_offload.stdout}")
                offload_stats = host2.run("ovs-appctl dpctl/offload-stats-show", job_level=ResultLevel.DEBUG)
                if offload_stats and offload_stats.stdout:
                    logging.debug(f"OVS Offload statistics:\n{offload_stats.stdout}")
                ports_dump = host2.run("ovs-ofctl dump-ports br0", job_level=ResultLevel.DEBUG)
                if ports_dump and ports_dump.stdout:
                    logging.debug(f"OVS Port statistics:\n{ports_dump.stdout}")
            except Exception as e:
                logging.debug(f"Error querying OVS statistics: {e}")

            self.perf_report_and_evaluate(result)
            return result
        finally:
            self.test_wide_deconfiguration(config)

    def _evaluate_dpctl_offload(self, host):
        if self.params.perf_test_simulation:
            logging.debug("Skipping offload evaluation in simulation mode")
            return

        res = host.run("ovs-appctl dpctl/dump-flows -m", job_level=ResultLevel.DEBUG)
        if not res or not res.stdout:
            self.add_result(
                ResultType.FAIL,
                "OVS DOCA offload evaluation failed: unable to query datapath flows",
            )
            return

        offloaded_pkts = 0
        non_offloaded_pkts = 0
        total_flows = 0
        offloaded_flows = 0

        for line in res.stdout.strip().splitlines():
            line = line.strip()
            if "packets:" not in line:
                continue

            m_pkts = re.search(r"packets:(\d+)", line)
            if not m_pkts:
                continue

            total_flows += 1
            pkts = int(m_pkts.group(1))

            if "offloaded:yes" in line:
                offloaded_pkts += pkts
                offloaded_flows += 1
            else:
                non_offloaded_pkts += pkts

        total_pkts = offloaded_pkts + non_offloaded_pkts
        if total_flows == 0 or total_pkts == 0:
            self.add_result(
                ResultType.FAIL,
                f"OVS DOCA offload evaluation failed: no packets or flows found in datapath "
                f"(flows={total_flows}, packets={total_pkts})",
            )
            return

        offload_ratio = (offloaded_pkts / total_pkts) * 100.0
        summary = (
            f"OVS DOCA datapath offload: {offloaded_pkts}/{total_pkts} packets "
            f"({offload_ratio:.2f}%) offloaded across {offloaded_flows}/{total_flows} flows "
            f"(threshold: >={self.params.min_offload_ratio}%)."
        )

        if offload_ratio >= self.params.min_offload_ratio:
            self.add_result(ResultType.PASS, f"PASS: {summary}")
        else:
            self.add_result(
                ResultType.FAIL,
                f"FAIL: Majority of packets were not offloaded to hardware. {summary}",
            )

    def test_wide_configuration(self, config):
        config.generator.host = self.matched.host1
        config.generator.nics.append(self.matched.host1.eth0)
        config.generator.nics.append(self.matched.host1.eth1)

        ipv4_addr = interface_addresses(self.params.net_ipv4)
        nic_addrs = {
            self.matched.host1.eth0: next(ipv4_addr),
            self.matched.host2.eth0: next(ipv4_addr),
            self.matched.host1.eth1: next(ipv4_addr),
            self.matched.host2.eth1: next(ipv4_addr),
        }
        for dev, addr in [
            (self.matched.host1.eth0, nic_addrs[self.matched.host1.eth0]),
            (self.matched.host1.eth1, nic_addrs[self.matched.host1.eth1]),
        ]:
            if addr not in dev.ips:
                try:
                    dev.ip_add(addr)
                except Exception:
                    dev.ip_flush()
                    dev.ip_add(addr)
        self.base_dpdk_configuration(config.generator)

        config.dut.host = self.matched.host2
        config.dut.nics.append(self.matched.host2.eth0)
        config.dut.nics.append(self.matched.host2.eth1)
        for dev, addr in [
            (self.matched.host2.eth0, nic_addrs[self.matched.host2.eth0]),
            (self.matched.host2.eth1, nic_addrs[self.matched.host2.eth1]),
        ]:
            if addr not in dev.ips:
                try:
                    dev.ip_add(addr)
                except Exception:
                    dev.ip_flush()
                    dev.ip_add(addr)

        self.base_doca_configuration(config)
        self.ovs_doca_bridge_configuration(config)

        self.init_guest_virtctl(config.dut, config.guest)
        self.shutdown_guest(config.guest)
        self.configure_guest_xml(config)

        guest = self.create_guest(config.dut, config.guest)

        if self.params.guest_driver == "vfio-pci":
            self.guest_vfio_modprobe(config.guest)
            self.base_dpdk_configuration(config.guest)
        else:
            guest.run(
                "modprobe mlx5_core; modprobe mlx5_ib || true",
                job_level=ResultLevel.DEBUG,
            )
            guest.run(
                "mkdir -p /dev/hugepages && mount -t hugetlbfs hugetlbfs /dev/hugepages 2>/dev/null || true",
                job_level=ResultLevel.DEBUG,
            )
            guest.run(
                "echo -n 1024 > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages || true",
                job_level=ResultLevel.DEBUG,
            )

        config.guest.testpmd = guest.run(
            TestPMD(
                coremask=self.params.guest_testpmd_cores,
                pmd_coremask=self.params.guest_dpdk_cores,
                forward_mode=self.params.doca_testpmd_forward_mode,
                nics=[nic.bus_info for nic in config.guest.nics],
                peer_macs=[nic.hwaddr for nic in config.generator.nics],
            ),
            bg=True,
        )

        time.sleep(5)
        return config

    def generate_perf_config(self, config):
        flows = []
        for src_nic, dst_nic in zip(config.generator.nics, config.dut.nics):
            src_bind = dict(
                mac_addr=src_nic.hwaddr,
                pci_addr=src_nic.bus_info,
                ip_addr=src_nic.ips[0],
                family=src_nic.ips[0].family,
            )
            dst_bind = dict(
                mac_addr=dst_nic.hwaddr,
                pci_addr=dst_nic.bus_info,
                ip_addr=dst_nic.ips[0],
                family=dst_nic.ips[0].family,
            )
            flows.append(
                PerfFlow(
                    type="UDPSimple",
                    generator=config.generator.host,
                    generator_nic=src_nic,
                    generator_bind=src_bind,
                    receiver=config.dut.host,
                    receiver_nic=dst_nic,
                    receiver_bind=dst_bind,
                    msg_size=self.params.perf_msg_size,
                    duration=self.params.perf_duration,
                    parallel_streams=self.params.perf_streams,
                    generator_cpupin=None,
                    receiver_cpupin=None,
                )
            )

        perf_recipe_conf = dict(recipe_config=config, flows=flows)

        cpu_measurement = self.params.cpu_perf_tool(
            [config.generator.host, config.dut.host, config.guest.host],
            perf_recipe_conf,
        )
        cores_list = [
            int(c.strip())
            for c in str(self.params.host1_dpdk_cores).split(",")
            if c.strip()
        ]
        flows_measurement = TRexFlowMeasurement(
            flows,
            self.params.trex_dir,
            cores_list,
            perf_recipe_conf,
        )
        perf_conf = PerfRecipeConf(
            measurements=[cpu_measurement, flows_measurement],
            iterations=self.params.perf_iterations,
            simulate_measurements=self.params.perf_test_simulation,
        )
        perf_conf.register_evaluators(cpu_measurement, self.cpu_perf_evaluators)
        perf_conf.register_evaluators(flows_measurement, self.net_perf_evaluators)
        return perf_conf

    def test_wide_deconfiguration(self, config):
        br_name = self.params.doca_bridge_name
        dut = config.dut
        host = dut.host

        try:
            self.guest_deconfigure(config.guest)
        except Exception:
            log_exc_traceback()

        try:
            self.shutdown_guest(config.guest)
            if config.guest.virtctl:
                config.guest.virtctl.vm_start(config.guest.name)
        except Exception:
            log_exc_traceback()

        try:
            if hasattr(dut, "vm_ports") and dut.vm_ports:
                for vm_port, _ in dut.vm_ports:
                    host.run(
                        f"ovs-vsctl del-port {br_name} {vm_port} || true",
                        job_level=ResultLevel.DEBUG,
                    )
            if hasattr(dut, "doca_ports") and dut.doca_ports:
                for dp_port, _ in dut.doca_ports:
                    host.run(
                        f"ovs-vsctl del-port {br_name} {dp_port} || true",
                        job_level=ResultLevel.DEBUG,
                    )
            host.run(f"ovs-vsctl del-br {br_name} || true", job_level=ResultLevel.DEBUG)
            host.run(
                "ovs-vsctl remove Open_vSwitch . other_config doca-init || true",
                job_level=ResultLevel.DEBUG,
            )
            host.run(
                "ovs-vsctl remove Open_vSwitch . other_config hw-offload || true",
                job_level=ResultLevel.DEBUG,
            )
            host.run(
                "ovs-vsctl remove Open_vSwitch . other_config userspace-tso-enable || true",
                job_level=ResultLevel.DEBUG,
            )
            host.run(
                "systemctl restart openvswitch || true",
                job_level=ResultLevel.DEBUG,
            )
        except Exception:
            log_exc_traceback()

        try:
            for nic in dut.nics:
                host.run(
                    f"echo 0 > /sys/bus/pci/devices/{nic.bus_info}/sriov_numvfs 2>/dev/null || "
                    f"echo 0 > /sys/class/net/{nic.name}/device/sriov_numvfs 2>/dev/null || true",
                    job_level=ResultLevel.DEBUG,
                )
        except Exception:
            log_exc_traceback()

        try:
            for pci_base, nic in getattr(dut, "configured_eswitch_devices", {}).items():
                try:
                    if nic.eswitch_mode != "legacy":
                        nic.eswitch_mode = "legacy"
                except Exception:
                    log_exc_traceback()
        except Exception:
            log_exc_traceback()

        try:
            hugepage_node = getattr(config, "hugepage_node", None)
            original_hugepages = getattr(config, "original_hugepages", None)
            if hugepage_node is not None and original_hugepages is not None:
                host.run(
                    f"echo {original_hugepages} > "
                    f"/sys/devices/system/node/node{hugepage_node}/hugepages/"
                    "hugepages-2048kB/nr_hugepages",
                    job_level=ResultLevel.DEBUG,
                )
        except Exception:
            log_exc_traceback()

        try:
            host.run(
                "service irqbalance start || true", job_level=ResultLevel.DEBUG
            )
        except Exception:
            log_exc_traceback()

        try:
            if self.params.driverctl_override:
                for nic in config.generator.nics:
                    config.generator.host.run(
                        f"driverctl unset-override {nic.bus_info} || true",
                        job_level=ResultLevel.DEBUG,
                    )
            config.generator.host.run(
                "service irqbalance start || true", job_level=ResultLevel.DEBUG
            )
        except Exception:
            log_exc_traceback()

    def base_doca_configuration(self, config):
        dut = config.dut
        host = dut.host

        host.run("service irqbalance stop")
        self._pin_irqs(host, 0)

        host.run(
            "grep -q '/dev/hugepages hugetlbfs' /proc/mounts || "
            "(mkdir -p /dev/hugepages && mount -t hugetlbfs hugetlbfs /dev/hugepages) || true",
            job_level=ResultLevel.DEBUG,
        )
        numa_node = self._detect_nic_numa_node(host, dut.nics[0])
        config.numa_node = numa_node
        hugepage_path = (
            f"/sys/devices/system/node/node{numa_node}/hugepages/"
            "hugepages-2048kB/nr_hugepages"
        )
        hugepage_count = host.run(f"cat {hugepage_path}", job_level=ResultLevel.DEBUG)
        try:
            config.hugepage_node = numa_node
            config.original_hugepages = int(hugepage_count.stdout.strip())
        except (AttributeError, TypeError, ValueError):
            raise LnstError(
                f"Could not read the existing hugepage count for NUMA node {numa_node}"
            )
        host.run(
            f"echo {self.params.nr_hugepages} > {hugepage_path}"
        )

        configured = {}
        for nic in dut.nics:
            if nic.bus_info not in configured:
                if nic.eswitch_mode != "switchdev":
                    nic.eswitch_mode = "switchdev"
                configured[nic.bus_info] = nic
        dut.configured_eswitch_devices = configured

        dut.sriov_devices = []
        dut.vfs = []
        dut.vf_reps = []
        dut.hostdev_vfs = []
        for nic in dut.nics:
            sriov_dev = SRIOVDevices(nic, 1)
            dut.sriov_devices.append(sriov_dev)
            dut.vfs.append(sriov_dev.vfs[0])
            dut.vf_reps.append(sriov_dev.vf_reps[0])
            dut.hostdev_vfs.append(
                HostdevDevice(
                    hwaddr=str(sriov_dev.vfs[0].hwaddr),
                    bus_info=str(sriov_dev.vfs[0].bus_info),
                )
            )

        for nic in dut.nics:
            nic.up()
        for vf_rep in dut.vf_reps:
            vf_rep.up()

    def ovs_doca_bridge_configuration(self, config):
        host = config.dut.host
        br_name = self.params.doca_bridge_name

        host.run("systemctl enable openvswitch")
        host.run("systemctl start openvswitch")
        host.run("ovs-vsctl --no-wait set Open_vSwitch . other_config:doca-init=true")
        host.run("ovs-vsctl --no-wait set Open_vSwitch . other_config:hw-offload=true")
        host.run(
            "ovs-vsctl --no-wait set Open_vSwitch . other_config:userspace-tso-enable=true"
        )
        host.run("systemctl restart openvswitch")

        host.run(
            f"ovs-vsctl add-br {br_name} -- set bridge {br_name} datapath_type=doca"
        )

        config.dut.doca_ports = []
        for i, nic in enumerate(config.dut.nics):
            port_name = nic.name
            ofport = f"1{i}"
            host.run(f"ip link set {port_name} up")
            host.run(
                f"ovs-vsctl add-port {br_name} {port_name} -- "
                f"set interface {port_name} type=doca ofport_request={ofport}"
            )
            config.dut.doca_ports.append((port_name, ofport))

        config.dut.vm_ports = []
        for i, vf_rep in enumerate(config.dut.vf_reps):
            port_name = vf_rep.name
            ofport = f"2{i}"
            host.run(f"ip link set {port_name} up")
            host.run(
                f"ovs-vsctl add-port {br_name} {port_name} -- "
                f"set interface {port_name} type=doca ofport_request={ofport}"
            )
            config.dut.vm_ports.append((port_name, ofport))

        host.run(f"ovs-ofctl del-flows {br_name}")
        for (dp_name, dp_ofport), (vm_name, vm_ofport) in zip(
            config.dut.doca_ports, config.dut.vm_ports
        ):
            host.run(
                f"ovs-ofctl add-flow {br_name} in_port={dp_ofport},action={vm_ofport}"
            )
            host.run(
                f"ovs-ofctl add-flow {br_name} in_port={vm_ofport},action={dp_ofport}"
            )

    def init_guest_xml(self, guest_conf):
        virtctl = guest_conf.virtctl
        guest_xml = ET.fromstring(virtctl.vm_XMLDesc(guest_conf.name))
        guest_conf.libvirt_xml = guest_xml
        return guest_xml

    def configure_guest_xml(self, config):
        guest_xml = self.init_guest_xml(config.guest)

        devices = guest_xml.find("devices")
        for vf in config.dut.hostdev_vfs:
            interface = ET.SubElement(
                devices, "interface", type="hostdev", managed="yes"
            )
            ET.SubElement(interface, "mac", address=str(vf.hwaddr))
            ET.SubElement(interface, "driver", name="vfio")
            source = ET.SubElement(interface, "source")

            pci_parts = vf.bus_info.replace(".", ":").split(":")
            if len(pci_parts) == 4:
                dom, bus, slot, func = pci_parts
            elif len(pci_parts) == 3:
                dom = "0000"
                bus, slot, func = pci_parts
            else:
                raise LnstError(f"Invalid PCI address format: {vf.bus_info}")

            ET.SubElement(
                source,
                "address",
                type="pci",
                domain=f"0x{dom}",
                bus=f"0x{bus}",
                slot=f"0x{slot}",
                function=f"0x{func}",
            )

        numa_node = getattr(config, "numa_node", 0)
        numa_cpus = self._get_numa_cpus(config.dut.host, numa_node)

        default_cpus = [
            int(c.strip()) for c in self.params.guest_cpus.split(",") if c.strip()
        ]
        if numa_cpus and not all(c in numa_cpus for c in default_cpus):
            # Pick CPUs from the NIC's NUMA node
            emulator_cpu = numa_cpus[0]
            guest_cpus = numa_cpus[1 : 1 + len(default_cpus)]
        elif numa_cpus:
            emulator_cpu = self.params.guest_emulatorpin_cpu
            guest_cpus = default_cpus
        else:
            emulator_cpu = self.params.guest_emulatorpin_cpu
            guest_cpus = default_cpus

        num_vcpus = len(guest_cpus) if guest_cpus else 1
        cpus_attr = f"0-{num_vcpus - 1}" if num_vcpus > 1 else "0"

        cputune = guest_xml.find("cputune")
        if cputune is None:
            cputune = ET.SubElement(guest_xml, "cputune")
        else:
            cputune.clear()
        for i, cpu_id in enumerate(guest_cpus):
            ET.SubElement(cputune, "vcpupin", vcpu=str(i), cpuset=str(cpu_id))
        ET.SubElement(cputune, "emulatorpin", cpuset=str(emulator_cpu))

        vcpu_elem = guest_xml.find("vcpu")
        if vcpu_elem is not None:
            vcpu_elem.text = str(num_vcpus)

        mem_elem = guest_xml.find("memory")
        if mem_elem is not None:
            mem_elem.text = str(self.params.guest_mem_size)
            mem_elem.set("unit", "KiB")

        cur_mem_elem = guest_xml.find("currentMemory")
        if cur_mem_elem is not None:
            cur_mem_elem.text = str(self.params.guest_mem_size)
            cur_mem_elem.set("unit", "KiB")

        cpu = guest_xml.find("cpu")
        if cpu is not None:
            numa = cpu.find("numa")
            if numa is None:
                numa = ET.SubElement(cpu, "numa")
            else:
                numa.clear()
            ET.SubElement(
                numa,
                "cell",
                id="0",
                cpus=cpus_attr,
                memory=str(self.params.guest_mem_size),
                unit="KiB",
                memAccess="shared",
            )

        numatune = guest_xml.find("numatune")
        if numatune is None:
            numatune = ET.SubElement(guest_xml, "numatune")
        else:
            numatune.clear()
        ET.SubElement(numatune, "memory", mode="strict", nodeset=str(numa_node))

        memoryBacking = guest_xml.find("memoryBacking")
        if memoryBacking is None:
            memoryBacking = ET.SubElement(guest_xml, "memoryBacking")
        else:
            memoryBacking.clear()
        hugepages = ET.SubElement(memoryBacking, "hugepages")
        # The hugepages page nodeset indexes guest NUMA cells; host placement
        # is controlled separately by the <numatune> nodeset above.
        ET.SubElement(hugepages, "page", size="2", unit="M", nodeset="0")
        ET.SubElement(memoryBacking, "source", type="file")
        ET.SubElement(memoryBacking, "access", mode="shared")
        ET.SubElement(memoryBacking, "allocation", mode="immediate")

        config.guest.libvirt_xml = guest_xml
        return guest_xml

    def create_guest(self, host_conf, guest_conf):
        host = host_conf.host
        virtctl = guest_conf.virtctl
        guest_xml = guest_conf.libvirt_xml

        str_xml = ET.tostring(guest_xml, encoding="utf8", method="xml")
        virtctl.createXML(str_xml.decode("utf8"))

        time.sleep(2)
        if not virtctl.is_vm_running(guest_conf.name):
            raise LnstError(f"Guest VM '{guest_conf.name}' failed to start with configured XML")

        guest_ip = None
        for _ in range(60):
            try:
                res = host.run(f"virsh domifaddr {guest_conf.name}", job_level=ResultLevel.DEBUG)
                if res and res.stdout:
                    m = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", res.stdout)
                    if m and not m.group(1).startswith("127."):
                        guest_ip = m.group(1)
                        break
            except Exception as e:
                logging.debug(f"virsh domifaddr error: {e}")
            try:
                guest_ip_job = host.run(f"gethostip -d {guest_conf.name}", job_level=ResultLevel.DEBUG)
                if guest_ip_job and guest_ip_job.stdout.strip():
                    ip_cand = guest_ip_job.stdout.strip()
                    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip_cand):
                        guest_ip = ip_cand
                        break
            except Exception as e:
                logging.debug(f"gethostip error: {e}")
            time.sleep(2)

        if not guest_ip:
            raise LnstError("Could not determine guest's IP address")

        guest = self.ctl.connect_host(guest_ip, timeout=60, machine_id="guest1")
        guest_conf.host = guest

        # Wait for Mellanox VF netdevs to be created and discovered inside the guest
        for vf in host_conf.hostdev_vfs:
            found = False
            for _ in range(15):
                res = guest.run(f"ip -br link show | grep -i '{vf.hwaddr}' || true", job_level=ResultLevel.DEBUG)
                if res and res.stdout.strip():
                    found = True
                    break
                time.sleep(2)
            if not found:
                ip_l = guest.run("ip -br link show", job_level=ResultLevel.DEBUG)
                logging.warning(
                    f"VF with MAC {vf.hwaddr} not found in guest. Guest links: {ip_l.stdout if ip_l else 'none'}"
                )

        guest_conf.nics = []
        for i, vf in enumerate(host_conf.hostdev_vfs):
            if not vf.hwaddr:
                raise LnstError("VF HW Address not configured")
            for retry in range(15):
                try:
                    guest.map_device(f"eth{i}", dict(hwaddr=vf.hwaddr))
                    break
                except Exception as e:
                    if retry == 14:
                        raise
                    time.sleep(1)
            device = getattr(guest, f"eth{i}")
            try:
                device.up()
            except Exception:
                pass
            guest_conf.nics.append(device)

        return guest

    def guest_vfio_modprobe(self, guest_conf):
        guest = guest_conf.host
        guest.run("modprobe -r vfio_iommu_type1 || true", job_level=ResultLevel.DEBUG)
        guest.run("modprobe -r vfio || true", job_level=ResultLevel.DEBUG)
        guest.run(
            "modprobe vfio enable_unsafe_noiommu_mode=1 || true",
            job_level=ResultLevel.DEBUG,
        )
        guest.run("modprobe vfio-pci || true", job_level=ResultLevel.DEBUG)

    def guest_deconfigure(self, guest_conf):
        guest = guest_conf.host
        if not guest:
            return

        testpmd = guest_conf.testpmd
        if testpmd:
            try:
                testpmd.kill(signal.SIGINT)
                testpmd.wait()
                if hasattr(testpmd, "result") and testpmd.result:
                    res_data = testpmd.result.get("res_data", {})
                    if res_data.get("stdout"):
                        logging.debug(f"TestPMD stdout:\n{res_data['stdout'].decode('utf-8', errors='replace')}")
                    if res_data.get("stderr"):
                        logging.debug(f"TestPMD stderr:\n{res_data['stderr'].decode('utf-8', errors='replace')}")
            except Exception as e:
                logging.debug(f"Error terminating TestPMD: {e}")

        if self.params.guest_driver == "vfio-pci":
            self.base_dpdk_deconfiguration(guest_conf)

    def check_sriov_capacity(self, host, nic, required_vfs=1):
        job = host.run(
            f"cat /sys/bus/pci/devices/{nic.bus_info}/sriov_totalvfs 2>/dev/null || "
            f"cat /sys/class/net/{nic.name}/device/sriov_totalvfs 2>/dev/null || echo 0"
        )
        try:
            total_vfs = int(job.stdout.strip())
        except (ValueError, TypeError):
            total_vfs = 0

        if total_vfs < required_vfs:
            raise LnstError(
                f"NIC {nic.name} ({nic.bus_info}) is improperly configured: "
                f"sriov_totalvfs is {total_vfs}, but at least {required_vfs} VF(s) are required. "
                f"Please enable SR-IOV in firmware (e.g. using 'mlxconfig -d {nic.bus_info} set SRIOV_EN=1 NUM_OF_VFS=8') "
                f"and reboot the machine."
            )

    def _detect_nic_numa_node(self, host, nic):
        job = host.run(
            f"cat /sys/bus/pci/devices/{nic.bus_info}/numa_node 2>/dev/null || echo 0"
        )
        try:
            node = int(job.stdout.strip())
            return node if node >= 0 else 0
        except (ValueError, TypeError):
            return 0

    def _get_numa_cpus(self, host, numa_node):
        job = host.run(
            f"cat /sys/devices/system/node/node{numa_node}/cpulist 2>/dev/null || echo ''",
            job_level=ResultLevel.DEBUG,
        )
        if job and job.stdout.strip():
            cpus = []
            for part in job.stdout.strip().split(","):
                part = part.strip()
                if not part:
                    continue
                if "-" in part:
                    start, end = part.split("-")
                    cpus.extend(range(int(start), int(end) + 1))
                else:
                    cpus.append(int(part))
            return cpus
        return []

    def _pin_irqs(self, host, cpu):
        mask = 1 << cpu
        host.run(
            "MASK={:x}; "
            "for i in `ls -d /proc/irq/[0-9]* 2>/dev/null` ; "
            "do echo $MASK > ${{i}}/smp_affinity 2>/dev/null || true; "
            "done".format(mask)
        )
