import xml.etree.ElementTree as ET
from enum import Enum

from lnst.Common.LnstError import LnstError
from lnst.Common.Parameters import Param, IntParam, StrParam
from lnst.Common.IpAddress import ipaddress
from lnst.RecipeCommon.Ping.Recipe import PingTestAndEvaluate
from lnst.Tests import Ping

from lnst.RecipeCommon.Perf.Recipe import Recipe as PerfRecipe
from lnst.RecipeCommon.LibvirtControl import LibvirtControl
from lnst.RecipeCommon.Perf.Measurements import StatCPUMeasurement

VirtioType = Enum('VirtType', 'VHOST_USER, VHOST_NET')


class VirtioDevice(object):
    """
    Virtio Device
    """
    def __init__(self, virt_type=None, hwaddr="", config=None):
        if not isinstance(virt_type, (VirtioType, None)):
            raise LnstError('Wrong virtio type')
        self.type = virt_type   # The virtio type
        self.hwaddr = hwaddr    # The MAC address of the device
        self.config = config    # Type-specific configuration


class BasePvPTestConf(object):
    class BaseHostConf(object):
        def __init__(self):
            self.host = None
            self.nics = []

    class BaseGuestConf(BaseHostConf):
        def __init__(self):
            super(BasePvPTestConf.BaseGuestConf, self).__init__()
            self.name = ""
            self.virtctl = None
            self.virtio_devs = []  # Array of VirtDevices

    def __init__(self, generator, dut, guest):
        self.generator = generator
        self.dut = dut
        self.guest = guest


class BasePvPRecipe(PingTestAndEvaluate, PerfRecipe):
    """
    Base PvP Recipe:
        TODO: Describe stages and configurations
    """

    driver = StrParam(mandatory=True)

    trex_dir = StrParam(mandatory=True)

    """
    Guest configuration parameters
    """
    guest_name = StrParam(mandatory=True)
    guest_cpus = StrParam(mandatory=True)
    guest_emulatorpin_cpu = StrParam(mandatory=True)
    guest_mem_size = IntParam(default=16777216)

    """
    Packet generator
    """

    """
    Perf tool configuration parameters
    """
    cpu_perf_tool = Param(default=StatCPUMeasurement)

    perf_duration = IntParam(default=60)
    perf_iterations = IntParam(default=5)
    perf_msg_size = IntParam(default=64)
    perf_parallel_streams = IntParam(default=1)

    nr_hugepages = IntParam(default=13000)
    # TODO: Allow 1G hugepages as well

    def warmup(self, ping_config):
        """ Generate warmup pings
        This ensures any in-between switches learn the corresponding MAC addresses
        Args:
            ping_config: array of tuples containing [OriginHost, OriginDevice, DestDevice].
        """
        try:
            self.warmup_configuration(ping_config)
            self.warmup_pings(ping_config)
        finally:
            self.warmup_deconfiguration(ping_config)

    def warmup_configuration(self, ping_config):
        if len(ping_config) > 255:
            raise LnstError("Too many warmup elements.")
        for i, elem in enumerate(ping_config):
            orig = elem[1]
            dest = elem[2]

            orig.ip_add(ipaddress('192.168.{}.1/24'.format(i)))
            dest.ip_add(ipaddress('192.168.{}.2/24'.format(i)))

            orig.up()
            dest.up()

    def warmup_pings(self, ping_config):
        jobs = []
        for i, elem in enumerate(ping_config):
            host = elem[0]
            orig = elem[1]
            dest = elem[2]
            jobs.append(host.run(Ping(interface=orig.ips[0], dst=dest.ips[0])))

        for job in jobs:
            job.wait()

        #  TODO eval

    def warmup_deconfiguration(self, ping_config):
        for i, elem in enumerate(ping_config):
            orig = elem[1]
            dest = elem[2]

            orig.ip_flush()
            dest.ip_flush()

    def base_dpdk_configuration(self, dpdk_host_cfg):
        """ Base DPDK configuration in a host
        Args:
            dpdk_host_cfg: An instance of BaseHostConf
        """
        host = dpdk_host_cfg.host

        for nic in dpdk_host_cfg.nics:
            nic.enable_readonly_cache()

        #  TODO service should be a host method
        host.run("service irqbalance stop")

        #  This will pin all irqs to cpu #0
        self._pin_irqs(host, 0)
        host.run("echo -n {} /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages"
                 .format(self.params.nr_hugepages))

        host.run("modprobe vfio-pci")
        for nic in dpdk_host_cfg.nics:
            host.run("driverctl set-override {} vfio-pci".format(nic.bus_info))

    def base_dpdk_deconfiguration(self, dpdk_host_cfg, service_list=[]):
        """ Undo Base DPDK configuration in a host
        Args:
            dpdk_host_cfg: An instance of BaseHostConf
            service_list: list of services using dpdk that might stop driverctl
                from being able to unset-override the host's interfaces.
                They will get restarted.
        """
        host = dpdk_host_cfg.host
        #  TODO service should be a host method
        host.run("service irqbalance start")
        for nic in dpdk_host_cfg.nics:
            job = host.run("driverctl unset-override {}".format(nic.bus_info),
                           bg=True)
            for service in service_list:
                host.run("systemctl restart {}". format(service))

            if not job.wait(10):
                job.kill()

    """
    Guest Management
    """
    def init_guest_virtctl(self, host_conf, guest_conf):
        """
        Initialize Libvirt Control
        Args:
            host_conf: An instance of BaseHostConf with the host info
            guest_conf: An instance of BaseGuestConf with the guest info
        """
        host = host_conf.host

        guest_conf.name = self.params.guest_name
        guest_conf.virtctl = host.init_class(LibvirtControl)

    def shutdown_guest(self, guest_conf):
        """ Shutdown a guest
        Args:
            guest_conf: An instance of BaseGuestConf with the guest info
        """
        virtctl = guest_conf.virtctl
        if virtctl:
            virtctl.vm_shutdown(guest_conf.name)
            self.ctl.wait_for_condition(lambda:
                                        not virtctl.is_vm_running(guest_conf.name))

    def init_guest_xml(self, guest_conf):
        """ Initialize the guest XML configuration with some basic values
        Args:
            guest_conf: An instance of BaseGuestConf with the guest info
        """
        virtctl = guest_conf.virtctl
        guest_xml = ET.fromstring(virtctl.vm_XMLDesc(guest_conf.name))
        guest_conf.libvirt_xml = guest_xml

        cputune = ET.SubElement(guest_xml, "cputune")
        for i, cpu_id in enumerate(self.params.guest_cpus.split(',')):
            ET.SubElement(cputune, "vcpupin", vcpu=str(i), cpuset=str(cpu_id))

        ET.SubElement(cputune,
                      "emulatorpin",
                      cpuset=str(self.params.guest_emulatorpin_cpu))

        return guest_xml

    def create_guest(self, host_conf, guest_conf):
        """ Create a guest
        Args:
            host_conf: The host_conf (instance of BaseHostConf)
            guest_conf: The host_conf (instance of BaseGuestConf)
            """
        host = host_conf.host
        virtctl = guest_conf.virtctl
        guest_xml = guest_conf.libvirt_xml

        str_xml = ET.tostring(guest_xml, encoding='utf8', method='xml')
        virtctl.createXML(str_xml.decode('utf8'))

        guest_ip_job = host.run("gethostip -d {}".format(guest_conf.name))
        guest_ip = guest_ip_job.stdout.strip()
        if not guest_ip:
            raise LnstError("Could not determine guest's IP address")

        guest = self.ctl.connect_host(guest_ip, timeout=60, machine_id="guest1")
        guest_conf.host = guest

        for i, vnic in enumerate(guest_conf.virtio_devs):
            if not vnic.hwaddr:
                raise LnstError("Virtio NIC HW Address not configured")
            guest.map_device("eth{}".format(i), dict(hwaddr=vnic.hwaddr))
            device = getattr(guest, "eth{}".format(i))
            guest_conf.nics.append(device)

        return guest

    def pvp_test(self, config):
        """ Perform the PvP test
        Args:
            config: An instance of BasePvPTestConf
        """
        try:
            self.test_wide_configuration(config)

            perf_config = self.generate_perf_config(config)
            result = self.perf_test(perf_config)
            self.perf_report_and_evaluate(result)
        finally:
            self.test_wide_deconfiguration(config)

    def _pin_irqs(self, host, cpu):
        mask = 1 << cpu
        host.run("MASK={:x}; "
                 "for i in `ls -d /proc/irq/[0-9]*` ; "
                    "do echo $MASK > ${{i}}/smp_affinity ; "
                 "done".format(mask))

    """
    Methods to be overridden
    """
    def generate_perf_config(self, config):
        """ Generate the perf configuration
        Args:
            config: The global test configuration
        Returns:
            An instance of Perf.Recipe.RecipeConf
        """
        pass

    def test_wide_deconfiguration(self, config):
        pass

    def test_wide_configuration(self, config):
        pass
