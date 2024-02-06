import xml.etree.ElementTree as ET

from lnst.Recipes.ENRT.BasePvPRecipe import BasePvPTestConf, BasePvPRecipe
from lnst.Recipes.ENRT.BasePvPRecipe import VirtioDevice, VirtioType
from lnst.Controller import HostReq, DeviceReq, RecipeParam

from lnst.Common.Logs import log_exc_traceback
from lnst.Common.Parameters import Param, StrParam, ParamError, IPv4NetworkParam
from lnst.Common.IpAddress import interface_addresses
from lnst.Devices import BridgeDevice

from lnst.RecipeCommon.Perf.Recipe import RecipeConf as PerfRecipeConf
from lnst.RecipeCommon.Perf.Measurements import Flow as PerfFlow
from lnst.RecipeCommon.Perf.Measurements import TRexFlowMeasurement
from lnst.RecipeCommon.Perf.Measurements import StatCPUMeasurement


class VhostPvPTestConf(BasePvPTestConf):
    def __init__(self):
        self.generator = self.BaseHostConf()
        self.dut = self.BaseHostConf()
        self.guest = self.BaseGuestConf()


class VhostNetPvPRecipe(BasePvPRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))
    host1.eth1 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    host2 = HostReq(with_guest="yes")
    host2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))
    host2.eth1 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    net_ipv4 = IPv4NetworkParam(default="192.168.101.0/24")

    host1_dpdk_cores = StrParam(mandatory=True)

    vhost_cpus = StrParam(mandatory=True)  # The CPUs used by vhost-net kernel threads

    # TODO: Study the possibility of adding more forwarding engines
    # like xdp or tc
    guest_fwd = StrParam(default='bridge')
    host_fwd = StrParam(default='bridge')

    guest_macs = Param(default=['02:fa:fe:fa:fe:01', '02:fa:fe:fa:fe:02'])

    generator_dpdk_cores = StrParam(mandatory=True)

    cpu_perf_tool = Param(default=StatCPUMeasurement)

    def test(self):
        self.check_params()

        config = VhostPvPTestConf()
        self.pvp_test(config)

    def check_params(self):
        # Check emulatorpin range contains vhost cores
        emulator_min, emulator_max = self.params.guest_emulatorpin_cpu.split('-')
        vhost_cpus = self.params.vhost_cpus.split(',')
        for vcpu in vhost_cpus:
            if vcpu > emulator_max or vcpu < emulator_min:
                raise ParamError("Emulator pin must contain vhost cpus")

    def gen_ping_config(self):
        return [
            (self.matched.host1,
             self.matched.host1.eth0,
             self.matched.host2.eth0),
            (self.matched.host1,
             self.matched.host1.eth1,
             self.matched.host2.eth1),
            (self.matched.host2,
             self.matched.host2.eth0,
             self.matched.host1.eth0),
            (self.matched.host2,
             self.matched.host2.eth1,
             self.matched.host2.eth1)
        ]

    def test_wide_configuration(self, config):

        config.generator.host = self.matched.host1
        config.generator.nics.append(self.matched.host1.eth0)
        config.generator.nics.append(self.matched.host1.eth1)

        ipv4_addr = interface_addresses(self.params.net_ipv4)
        self.matched.host1.eth0.ip_add(next(ipv4_addr))
        self.matched.host1.eth1.ip_add(next(ipv4_addr))
        self.matched.host1.eth0.up()
        self.matched.host1.eth1.up()

        self.base_dpdk_configuration(config.generator)

        config.dut.host = self.matched.host2
        config.dut.nics.append(self.matched.host2.eth0)
        config.dut.nics.append(self.matched.host2.eth1)
        self.matched.host2.eth0.up()
        self.matched.host2.eth1.up()

        self.host_forwarding_configuration(config.dut)

        self.init_guest_virtctl(config.dut, config.guest)
        self.shutdown_guest(config.guest)
        self.configure_guest_xml(config.dut, config.guest)

        self.create_guest(config.dut, config.guest)
        self.guest_forwarding(config.guest)

        self.host_forwarding_vm_configuration(config.dut, config.guest)

        return config

    def generate_perf_config(self, config):
        flows = []
        for i in range(0, min(len(config.generator.nics),
                              len(config.guest.nics))):
            src_nic = config.generator.nics[i]
            src_ip = src_nic.ips[0]
            dst_nic = config.guest.nics[i]
            dst_ip = config.generator.nics[((i + 1) % len(config.generator.nics))].ips[0]

            src_bind = dict(mac_addr=src_nic.hwaddr,
                            pci_addr=src_nic.bus_info,
                            ip_addr=src_ip)
            dst_bind = dict(mac_addr=dst_nic.hwaddr,
                            pci_addr=dst_nic.bus_info,
                            ip_addr=dst_ip)
            flows.append(PerfFlow(type="pvp_loop_rate",
                                  generator=config.generator.host,
                                  generator_bind=src_bind,
                                  receiver=config.guest.host,
                                  receiver_bind=dst_bind,
                                  msg_size=self.params.perf_msg_size,
                                  duration=self.params.perf_duration,
                                  parallel_streams=self.params.perf_streams,
                                  generator_cpupin=None,
                                  receiver_cpupin=None)
                         )

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
            self.host_forwarding_vm_deconfiguration(config.dut, config.guest)
        except:
            log_exc_traceback()

        try:
            self.host_forwarding_deconfiguration(config.dut)
        except:
            log_exc_traceback()

        try:
            self.base_dpdk_deconfiguration(config.generator)
        except:
            log_exc_traceback()

        try:
            #returning the guest to the original running state
            self.shutdown_guest(config.guest)
            if config.guest.virtctl:
                config.guest.virtctl.vm_start(config.guest.name)
        except:
            log_exc_traceback()

        try:
            config.generator.host.run("service irqbalance start")
        except:
            log_exc_traceback()

    def host_forwarding_vm_configuration(self, host_conf, guest_conf):
        """
        VM - specific forwarding configuration
        Pin vhost-net kernel threads to the cpus specfied by vhost_cpus param
        """
        # Get a comma separated list of the vhost-net kernel threads' PIDs
        vhost_pids = host_conf.host.run(
                """ ps --ppid 2 | grep "vhost-$(pidof qemu-kvm)" """
                """ | awk '{if (length(pidstring) == 0) { """
                """     pidstring=$1 """
                """ } else { """
                """     pidstring = sprintf("%s,%s", pidstring, $1) """
                """ }}; """
                """ END{ print pidstring }'""")
        for pid, cpu in zip(vhost_pids.stdout.strip().split(','),
                            self.params.vhost_cpus.split(',')):
            mask = 1 << int(cpu)
            host_conf.host.run('taskset -p {:x} {}'.format(mask, pid))

    def host_forwarding_vm_deconfiguration(self, host_conf, guest_conf):
        """
        VM - specific forwarding deconfiguration
        """
        pass

    def host_forwarding_configuration(self, host_conf):
        if (self.params.host_fwd == 'bridge'):
            host_conf.bridges = []
            host_conf.host.br0 = BridgeDevice()
            host_conf.host.br1 = BridgeDevice()

            host_conf.host.br0.slave_add(host_conf.nics[0])
            host_conf.host.br1.slave_add(host_conf.nics[1])

            host_conf.host.br0.up()
            host_conf.host.br1.up()

            host_conf.bridges.append(host_conf.host.br0)
            host_conf.bridges.append(host_conf.host.br1)

        else:
            # TBD
            return

    def host_forwarding_deconfiguration(self, host_conf):
        if (self.params.host_fwd == 'bridge'):
            if host_conf.host.br0:
                host_conf.host.br0.slave_del(
                    host_conf.nics[0])
            if host_conf.host.br1:
                host_conf.host.br1.slave_del(
                    host_conf.nics[1])
        else:
            # TBD
            return

    def configure_guest_xml(self, host_conf, guest_conf):
        guest_xml = self.init_guest_xml(guest_conf)

        virtctl = guest_conf.virtctl
        guest_xml = ET.fromstring(virtctl.vm_XMLDesc(guest_conf.name))
        guest_conf.libvirt_xml = guest_xml

        guest_conf.virtio_devs = []
        for i, nic in enumerate(host_conf.nics):
            self._xml_add_vhostnet_dev(guest_xml,
                                       "vhostnet-{i}".format(i=i),
                                       host_conf.bridges[i],
                                       self.params.guest_macs[i])

            vhost_device = VirtioDevice(VirtioType.VHOST_NET,
                                        self.params.guest_macs[i],
                                        config={
                                            "bridge": host_conf.bridges[i]
                                        }
                                        )
            guest_conf.virtio_devs.append(vhost_device)

        return guest_xml

    def guest_forwarding(self, guest_conf):
        guest = guest_conf.host
        if (self.params.guest_fwd == 'bridge'):
            guest.bridge = BridgeDevice()
            guest.bridge.name = 'guestbr0'
            for nic in guest_conf.nics:
                guest.bridge.slave_add(nic)
                nic.up()

        guest.run("echo 1 > /proc/sys/net/ipv4/ip_forward")

    def guest_deconfigure(self, guest_conf):
        if guest_conf.host:
            guest_conf.host.run("echo 0 > /proc/sys/net/ipv4/ip_forward")

    def _xml_add_vhostnet_dev(self, guest_xml, name, bridge, mac_addr):
        devices = guest_xml.find("devices")

        interface = ET.SubElement(devices, 'interface', type='bridge')
        ET.SubElement(interface, 'source', bridge=str(bridge.name))
        ET.SubElement(interface, 'mac', address=str(mac_addr))
        ET.SubElement(interface, 'model', type='virtio')
        ET.SubElement(interface, 'driver', name='vhost')
        # TODO: Add driver suboptions
        return guest_xml
