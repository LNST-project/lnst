import logging
import time
import signal
import xml.etree.ElementTree as ET

from lnst.Recipes.ENRT.BasePvPRecipe import BasePvPTestConf, BasePvPRecipe
from lnst.Recipes.ENRT.BasePvPRecipe import VirtioDevice, VirtioType
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.Parameters import Param, IntParam, StrParam, BoolParam
from lnst.Common.IpAddress import ipaddress
from lnst.RecipeCommon.Ping.Recipe import PingTestAndEvaluate, PingConf
from lnst.Tests import Ping
from lnst.Tests.TestPMD import TestPMD

from lnst.RecipeCommon.Perf.Recipe import Recipe as PerfRecipe
from lnst.RecipeCommon.Perf.Recipe import RecipeConf as PerfRecipeConf
from lnst.RecipeCommon.Perf.Measurements import Flow as PerfFlow
from lnst.RecipeCommon.Perf.Measurements import TRexFlowMeasurement
from lnst.RecipeCommon.Perf.Measurements import StatCPUMeasurement

from lnst.RecipeCommon.LibvirtControl import LibvirtControl

from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration

class OVSPvPTestConf(BasePvPTestConf):
    class DUTConf(BasePvPTestConf.BaseHostConf):
        def __init__(self):
            super(OVSPvPTestConf.DUTConf, self).__init__()
            self.trex_path = ""
            self.dpdk_ports = None
            self.vm_ports = None

    class GuestConf(BasePvPTestConf.BaseGuestConf):
        def __init__(self):
            super(OVSPvPTestConf.GuestConf, self).__init__()
            self.testpmd = None

    def __init__(self):
        self.generator = self.BaseHostConf()
        self.dut = self.DUTConf()
        self.guest = self.GuestConf()


class OvSDPDKPvPRecipe(BasePvPRecipe):
    m1 = HostReq()
    m1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))
    m1.eth1 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    m2 = HostReq(with_guest="yes")
    m2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))
    m2.eth1 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    guest_dpdk_cores = StrParam(mandatory=True)
    guest_testpmd_cores = StrParam(mandatory=True)

    host1_dpdk_cores = StrParam(mandatory=True)
    host2_pmd_cores = StrParam(mandatory=True)
    host2_l_cores = StrParam(mandatory=True)
    socket_mem = IntParam(default=2048)

    cpu_perf_tool = Param(default=StatCPUMeasurement)

    perf_duration = IntParam(default=60)
    perf_iterations = IntParam(default=5)
    perf_msg_size = IntParam(default=64)

    #doesn't do anything for now...
    perf_streams = IntParam(default=1)

    def test(self):
        self.check_dependencies()
        ping_config = self.gen_ping_config()
        self.warmup(ping_config)

        config = OVSPvPTestConf()
        self.pvp_test(config)

    def check_dependencies(self):
        pass

    def gen_ping_config(self):
        return [
            (self.matched.m1, self.matched.m1.eth0, self.matched.m2.eth0),
            (self.matched.m1, self.matched.m1.eth1, self.matched.m2.eth1),
            (self.matched.m2, self.matched.m2.eth0, self.matched.m1.eth0),
            (self.matched.m2, self.matched.m2.eth1, self.matched.m2.eth1)
        ]

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
        flows = []
        for src_nic, dst_nic in zip(config.generator.nics, config.dut.nics):
            src_bind = dict(mac_addr=src_nic.hwaddr,
                            pci_addr=src_nic.bus_info,
                            ip_addr=src_nic.ips[0])
            dst_bind = dict(mac_addr=dst_nic.hwaddr,
                            pci_addr=dst_nic.bus_info,
                            ip_addr=dst_nic.ips[0])
            flows.append(PerfFlow(
                type="pvp_loop_rate",
                generator=config.generator.host,
                generator_bind=src_bind,
                receiver=config.dut.host,
                receiver_bind=dst_bind,
                msg_size=self.params.perf_msg_size,
                duration=self.params.perf_duration,
                parallel_streams=self.params.perf_streams,
                cpupin=None))

        return PerfRecipeConf(
            measurements=[
                self.params.cpu_perf_tool(
                    [config.generator.host, config.dut.host, config.guest.host]
                ),
                TRexFlowMeasurement(
                    flows,
                    self.params.trex_dir,
                    self.params.host1_dpdk_cores.split(","),
                ),
            ],
            iterations=self.params.perf_iterations,
        )

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

            self.base_dpdk_deconfiguration(config.dut, ["openvswitch"])
        except:
            log_exc_traceback()

        try:
            #  returning the guest to the original running state
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

        #  TODO use an actual OvS Device object
        #  TODO config.dut.nics.append(CachedRemoteDevice(m2.ovs))
        host.run("ovs-vsctl add-br br0 -- set bridge br0 datapath_type=netdev")

        host_conf.dpdk_ports = []
        for i, nic in enumerate(host_conf.nics):
            host.run("ovs-vsctl add-port br0 dpdk{i} -- "
                     "set interface dpdk{i} type=dpdk ofport_request=1{i} "
                     "options:dpdk-devargs={pci_addr}".format(
                         i=i, pci_addr=nic.bus_info))
            host_conf.dpdk_ports.append(
                    ("dpdk{}".format(i), "1{}".format(i)))

    def configure_guest_xml(self, host_conf, guest_conf):
        #  Initialize guest XML
        guest_xml = self.init_guest_xml(guest_conf)

        guest_conf.virtio_devs = []
        for i, nic in enumerate(host_conf.nics):
            path = self._xml_add_vhostuser_dev(guest_xml,
                                               "vhost_nic{i}".format(i=i),
                                               nic.hwaddr)

            virtio_dev = VirtioDevice(VirtioType.VHOST_USER,
                                      str(nic.hwaddr),
                                      config={
                                          "path": path
                                      }
                                      )
            guest_conf.virtio_devs.append(virtio_dev)

        cpu = guest_xml.find("cpu")
        numa = ET.SubElement(cpu, 'numa')
        ET.SubElement(numa, 'cell', id='0', cpus='0',
                      memory=str(self.params.guest_mem_size), unit='KiB',
                      memAccess='shared')

        memoryBacking = ET.SubElement(guest_xml, "memoryBacking")
        hugepages = ET.SubElement(memoryBacking, "hugepages")
        ET.SubElement(hugepages, "page", size="2", unit="M", nodeset="0")

        return guest_xml

    def ovs_dpdk_bridge_vm_configuration(self, host_conf, guest_conf):
        host = host_conf.host
        host_conf.vm_ports = []
        for i, vhuser_nic in enumerate(guest_conf.virtio_devs):
            host.run(
                "ovs-vsctl add-port br0 guest_nic{i} -- "
                "set interface guest_nic{i} type=dpdkvhostuserclient "
                "ofport_request=2{i} "
                "options:vhost-server-path={path}".format(
                    i=i, path=vhuser_nic.config.get("path")))
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
        if testpmd:
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
