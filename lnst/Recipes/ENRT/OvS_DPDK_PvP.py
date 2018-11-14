import logging
import time
import signal
import xml.etree.ElementTree as ET

from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.Parameters import Param, IntParam, StrParam, BoolParam
from lnst.Common.IpAddress import ipaddress
from lnst.RecipeCommon.Ping import PingTestAndEvaluate, PingConf
from lnst.Tests import Ping
from lnst.Tests.TestPMD import TestPMD
from lnst.RecipeCommon.Perf import PerfTestAndEvaluate, PerfConf
from lnst.RecipeCommon.TRexMeasurementTool import TRexMeasurementTool

from lnst.RecipeCommon.LibvirtControl import LibvirtControl

from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration

class PvPTestConf(object):
    class HostConf(object):
        def __init__(self):
            self.host = None
            self.nics = []

    class DUTConf(HostConf):
        def __init__(self):
            super(PvPTestConf.DUTConf, self).__init__()
            self.trex_path = ""
            self.dpdk_ports = None
            self.vm_ports = None

    class GuestConf(HostConf):
        def __init__(self):
            super(PvPTestConf.GuestConf, self).__init__()
            self.name = ""
            self.virtctl = None
            self.testpmd = None
            self.vhost_nics = None

    def __init__(self):
        self.generator = self.HostConf()
        self.dut = self.DUTConf()
        self.guest = self.GuestConf()

class OvSDPDKPvPRecipe(PingTestAndEvaluate, PerfTestAndEvaluate):
    m1 = HostReq()
    m1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))
    m1.eth1 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    m2 = HostReq(has_guest="True")
    m2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))
    m2.eth1 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    driver = StrParam(mandatory=True)

    trex_dir = StrParam(mandatory=True)

    guest_name = StrParam(mandatory=True)
    guest_cpus = StrParam(mandatory=True)
    guest_emulatorpin_cpu = StrParam(mandatory=True)
    guest_dpdk_cores = StrParam(mandatory=True)
    guest_testpmd_cores = StrParam(mandatory=True)
    guest_mem_size = IntParam(default=16777216)

    host1_dpdk_cores = StrParam(mandatory=True)
    host2_pmd_cores = StrParam(mandatory=True)
    host2_l_cores = StrParam(mandatory=True)
    nr_hugepages = IntParam(default=13000)
    socket_mem = IntParam(default=2048)

    dev_intr_cpu = IntParam(default=0)


    perf_duration = IntParam(default=60)
    perf_iterations = IntParam(default=5)
    perf_msg_size = IntParam(default=64)

    #doesn't do anything for now...
    perf_streams = IntParam(default=1)

    perf_usr_comment = StrParam(default="")

    def test(self):
        self.check_dependencies()
        self.warmup()
        self.pvp_test()

    def check_dependencies(self):
        pass

    def warmup(self):
        try:
            self.warmup_configuration()
            self.warmup_pings()
        finally:
            self.warmup_deconfiguration()

    def warmup_configuration(self):
        m1, m2 = self.matched.m1, self.matched.m2
        m1.eth0.ip_add(ipaddress("192.168.1.1/24"))
        m1.eth1.ip_add(ipaddress("192.168.1.3/24"))

        m2.eth0.ip_add(ipaddress("192.168.1.2/24"))
        m2.eth1.ip_add(ipaddress("192.168.1.4/24"))

    def warmup_pings(self):
        m1, m2 = self.matched.m1, self.matched.m2

        jobs = []
        jobs.append(m1.run(Ping(interface=m1.eth0.ips[0], dst=m2.eth0.ips[0]), bg=True))
        jobs.append(m1.run(Ping(interface=m1.eth1.ips[0], dst=m2.eth1.ips[0]), bg=True))
        jobs.append(m2.run(Ping(interface=m2.eth0.ips[0], dst=m1.eth0.ips[0]), bg=True))
        jobs.append(m2.run(Ping(interface=m2.eth1.ips[0], dst=m1.eth1.ips[0]), bg=True))

        for job in jobs:
            job.wait()
        #TODO eval

    def warmup_deconfiguration(self):
        m1, m2 = self.matched.m1, self.matched.m2
        m1.eth0.ip_flush()
        m1.eth1.ip_flush()

        m2.eth0.ip_flush()
        m2.eth1.ip_flush()

    def pvp_test(self):
        try:
            config = PvPTestConf()
            self.test_wide_configuration(config)

            perf_config = self.generate_perf_config(config)
            result = self.perf_test(perf_config)
            self.perf_evaluate_and_report(perf_config, result, baseline=None)
        finally:
            self.test_wide_deconfiguration(config)

    def test_wide_configuration(self, config):
        config.generator.host = self.matched.m1
        config.generator.nics.append(self.matched.m1.eth0)
        config.generator.nics.append(self.matched.m1.eth1)
        self.matched.m1.eth0.ip_add(ipaddress("192.168.1.1/24"))
        self.matched.m1.eth1.ip_add(ipaddress("192.168.1.3/24"))
        self.base_dpdk_configuration(config.generator)

        config.dut.host = self.matched.m2
        config.dut.nics.append(self.matched.m2.eth0)
        config.dut.nics.append(self.matched.m2.eth1)
        self.matched.m2.eth0.ip_add(ipaddress("192.168.1.2/24"))
        self.matched.m2.eth1.ip_add(ipaddress("192.168.1.4/24"))
        self.base_dpdk_configuration(config.dut)
        self.ovs_dpdk_bridge_configuration(config.dut)

        self.init_guest_virtctl(config.dut, config.guest)
        self.shutdown_guest(config.guest)
        self.configure_guest_xml(config.dut, config.guest)

        self.ovs_dpdk_bridge_vm_configuration(config.dut, config.guest)
        self.ovs_dpdk_bridge_flow_configuration(config.dut)

        guest = self.create_guest(config.dut, config.guest)
        self.guest_vfio_modprobe(config.guest)
        self.base_dpdk_configuration(config.guest)

        config.guest.testpmd = guest.run(
                TestPMD(
                    coremask=self.params.guest_testpmd_cores,
                    pmd_coremask=self.params.guest_dpdk_cores,
                    nics=[nic.bus_info for nic in config.guest.nics],
                    peer_macs=[nic.hwaddr for nic in config.generator.nics]),
                bg=True)

        time.sleep(5)
        return config

    def generate_perf_config(self, config):
        conf = PerfConf(
                perf_tool = TRexMeasurementTool(self.params.trex_dir),
                test_type = "pvp_loop_rate",
                generator = config.generator.host,
                generator_bind = config.generator.nics,
                receiver = config.dut.host,
                receiver_bind = config.dut.nics,
                msg_size = self.params.perf_msg_size,
                duration = self.params.perf_duration,
                iterations = self.params.perf_iterations,
                streams = self.params.perf_streams)
        return conf

    def test_wide_deconfiguration(self, config):
        try:
            self.guest_deconfigure(config.guest)
        except:
            log_exc_traceback()

        try:
            config.dut.host.run("ovs-ofctl del-flows br0")
            for vm_port, port_id in config.dut.vm_ports:
                config.dut.host.run("ovs-vsctl del-port br0 {}".format(vm_port))
            for dpdk_port, port_id in config.dut.dpdk_ports:
                config.dut.host.run("ovs-vsctl del-port br0 {}".format(dpdk_port))
            config.dut.host.run("ovs-vsctl del-br br0")
            config.dut.host.run("service openvswitch restart")

            self.base_dpdk_deconfiguration(config.dut)
        except:
            log_exc_traceback()

        try:
            #returning the guest to the original running state
            self.shutdown_guest(config.guest)
            config.guest.virtctl.vm_start(config.guest.name)
        except:
            log_exc_traceback()

        try:
            for nic in config.generator.nics:
                config.generator.host.run(
                    "driverctl unset-override {}".format(nic.bus_info))

            config.generator.host.run("service irqbalance start")
        except:
            log_exc_traceback()

    def base_dpdk_configuration(self, dpdk_host_cfg):
        host = dpdk_host_cfg.host

        for nic in dpdk_host_cfg.nics:
            nic.enable_readonly_cache()

        #TODO service should be a host method
        host.run("service irqbalance stop")

        # this will pin all irqs to cpu #0
        self._pin_irqs(host, 0)
        host.run("echo -n {} /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages"
               .format(self.params.nr_hugepages))

        host.run("modprobe vfio-pci")
        for nic in dpdk_host_cfg.nics:
            host.run("driverctl set-override {} vfio-pci".format(nic.bus_info))

    def base_dpdk_deconfiguration(self, dpdk_host_cfg):
        host = dpdk_host_cfg.host
        #TODO service should be a host method
        host.run("service irqbalance start")
        for nic in dpdk_host_cfg.nics:
            job = host.run("driverctl unset-override {}".format(nic.bus_info),
                           bg=True)
            if isinstance(dpdk_host_cfg, PvPTestConf.DUTConf):
                host.run("systemctl restart openvswitch")

            if not job.wait(10):
                job.kill()

    def ovs_dpdk_bridge_configuration(self, host_conf):
        host = host_conf.host
        host.run("systemctl enable openvswitch")
        host.run("systemctl start openvswitch")
        host.run("ovs-vsctl --no-wait set Open_vSwitch . other_config:dpdk-init=true")
        host.run("ovs-vsctl --no-wait set Open_vSwitch . other_config:dpdk-socket-mem={}"
                 .format(self.params.socket_mem))
        host.run("ovs-vsctl --no-wait set Open_vSwitch . other_config:pmd-cpu-mask={}"
                 .format(self.params.host2_pmd_cores))
        host.run("ovs-vsctl --no-wait set Open_vSwitch . other_config:dpdk-lcore-mask={}"
                 .format(self.params.host2_l_cores))
        host.run("systemctl restart openvswitch")

        host.run("systemctl restart openvswitch")

        #TODO use an actual OvS Device object
        #TODO config.dut.nics.append(CachedRemoteDevice(m2.ovs))
        host.run("ovs-vsctl add-br br0 -- set bridge br0 datapath_type=netdev")

        host_conf.dpdk_ports = []
        for i, nic in enumerate(host_conf.nics):
            host.run("ovs-vsctl add-port br0 dpdk{i} -- "
                     "set interface dpdk{i} type=dpdk ofport_request=1{i} "
                     "options:dpdk-devargs={pci_addr}".format(
                         i=i, pci_addr=nic.bus_info))
            host_conf.dpdk_ports.append(
                    ("dpdk{}".format(i), "1{}".format(i)))

    def init_guest_virtctl(self, host_conf, guest_conf):
        host = host_conf.host

        guest_conf.name = self.params.guest_name
        guest_conf.virtctl = host.init_class(LibvirtControl)

    def shutdown_guest(self, guest_conf):
        virtctl = guest_conf.virtctl
        virtctl.vm_shutdown(guest_conf.name)
        self.ctl.wait_for_condition(lambda:
            not virtctl.is_vm_running(guest_conf.name))

    def configure_guest_xml(self, host_conf, guest_conf):
        virtctl = guest_conf.virtctl
        guest_xml = ET.fromstring(virtctl.vm_XMLDesc(guest_conf.name))
        guest_conf.libvirt_xml = guest_xml

        guest_conf.vhost_nics = []
        vhosts = guest_conf.vhost_nics
        for i, nic in enumerate(host_conf.nics):
            path = self._xml_add_vhostuser_dev(
                    guest_xml, "vhost_nic{i}".format(i=i), nic.hwaddr)
            vhosts.append((path, nic.hwaddr))

        cpu = guest_xml.find("cpu")
        numa = ET.SubElement(cpu, 'numa')
        ET.SubElement(numa, 'cell', id='0', cpus='0',
                      memory=str(self.params.guest_mem_size), unit='KiB',
                      memAccess='shared')

        cputune = ET.SubElement(guest_xml, "cputune")
        for i, cpu_id in enumerate(self.params.guest_cpus.split(',')):
            ET.SubElement(cputune, "vcpupin", vcpu=str(i), cpuset=str(cpu_id))

        ET.SubElement(cputune,
                      "emulatorpin",
                      cpuset=str(self.params.guest_emulatorpin_cpu))

        memoryBacking = ET.SubElement(guest_xml, "memoryBacking")
        hugepages = ET.SubElement(memoryBacking, "hugepages")
        ET.SubElement(hugepages, "page", size="2", unit="M", nodeset="0")

        return guest_xml

    def ovs_dpdk_bridge_vm_configuration(self, host_conf, guest_conf):
        host = host_conf.host
        host_conf.vm_ports = []
        for i, nic in enumerate(guest_conf.vhost_nics):
            host.run(
                "ovs-vsctl add-port br0 guest_nic{i} -- "
                "set interface guest_nic{i} type=dpdkvhostuserclient "
                "ofport_request=2{i} "
                "options:vhost-server-path={path}".format(
                    i=i, path=nic[0]))
            host_conf.vm_ports.append(
                    ("guest_nic{}".format(i), "2{}".format(i)))

    def ovs_dpdk_bridge_flow_configuration(self, host_conf):
        host = host_conf.host
        host.run("ovs-ofctl del-flows br0")
        for dpdk_port, vm_port in zip(host_conf.dpdk_ports, host_conf.vm_ports):
            host.run("ovs-ofctl add-flow br0 in_port={},action={}"
                     .format(dpdk_port[1], vm_port[1]))
            host.run("ovs-ofctl add-flow br0 in_port={},action={}"
                     .format(vm_port[1], dpdk_port[1]))

    def create_guest(self, host_conf, guest_conf):
        host = host_conf.host
        virtctl = guest_conf.virtctl
        guest_xml = guest_conf.libvirt_xml

        virtctl.createXML(ET.tostring(guest_xml))

        guest_ip_job = host.run("gethostip -d {}".format(guest_conf.name))
        guest_ip = guest_ip_job.stdout.strip()

        guest = self.ctl.connect_host(guest_ip, timeout=60)
        guest_conf.host = guest

        for i, nic in enumerate(guest_conf.vhost_nics):
            guest.map_device("eth{}".format(i), dict(hwaddr=nic[1]))
            device = getattr(guest, "eth{}".format(i))
            guest_conf.nics.append(device)
        return guest

    def guest_vfio_modprobe(self, guest_conf):
        guest = guest_conf.host
        guest.run("modprobe -r vfio_iommu_type1")
        guest.run("modprobe -r vfio")
        guest.run("modprobe vfio enable_unsafe_noiommu_mode=1")
        guest.run("modprobe vfio-pci")

    def guest_deconfigure(self, guest_conf):
        guest = guest_conf.host
        if not guest:
            return

        testpmd = guest_conf.testpmd
        if testpmd and not testpmd.finished:
            testpmd.kill(signal.SIGINT)
            testpmd.wait()

        self.base_dpdk_deconfiguration(guest_conf)

    def _xml_add_vhostuser_dev(self, guest_xml, name, mac_addr):
        vhost_server_path = "/tmp/{}".format(name)
        devices = guest_xml.find("devices")

        interface = ET.SubElement(devices, 'interface', type='vhostuser')
        ET.SubElement(interface, 'mac', address=str(mac_addr))
        ET.SubElement(interface, 'model', type='virtio')
        ET.SubElement(interface, 'source', type='unix',
                      path=vhost_server_path, mode='server')
        return vhost_server_path

    def _pin_irqs(self, host, cpu):
        mask = 1 << cpu
        host.run("MASK={:x}; "
                 "for i in `ls -d /proc/irq/[0-9]*` ; "
                    "do echo $MASK > ${{i}}/smp_affinity ; "
                 "done".format(cpu))
