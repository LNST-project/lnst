import signal
from lnst.Common.Parameters import (
    StrParam,
    IntParam,
    Param,
    IPv4NetworkParam,
    IPv6NetworkParam,
)
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Controller.Namespace import Namespace
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from dataclasses import dataclass
from lnst.Common.IpAddress import interface_addresses
from lnst.Tests.TestPMD import TestPMD

from lnst.RecipeCommon.Perf.Recipe import RecipeConf as PerfRecipeConf
from lnst.RecipeCommon.Perf.Measurements import Flow as PerfFlow
from lnst.RecipeCommon.Perf.Measurements import TRexFlowMeasurement
from lnst.RecipeCommon.Perf.Measurements import StatCPUMeasurement


@dataclass
class DummyEthDevice:
    """
    Auxiliary class to store Ethernet related information,
    that are no longer available for kernel, therefore LNST Device
    class can no longer be used.
    """
    bus_info: str
    hwaddr: str
    _id: str
    ips: list


@dataclass
class DummyRecipeConfig:
    """
    Auxiliary class to store network related information
    required for the recipe configuration.
    """
    eth0: DummyEthDevice
    eth1: DummyEthDevice
    netns: Namespace
    testpmd: None
    test_br: str = "test_bridge"
    bond_br: str = "bond_bridge"


class OvSDPDKBondRecipe(BaseEnrtRecipe):
    """
    This recipe implements Enrt testing for OvS DPDK Bonding recipe
    network scenario that looks as follows

    .. code-block:: none

                                         +--------+
                     +-------------------+        +----------------------+
                     |                   | switch |                      |
                     |          +--------+        +------------+         |
                     |          |        +--------+            |         |
                     |          |                              |         |
     +---------------|----------|----------------+             |         |
     |        +------|----------|-------+        |       +-----|---------|-----+
     |        | +----|-dpdkbond-|-----+ |        |       | +---+---+ +---+---+ |
     |        | | +--+----+ +---+---+ | |        |       | | dpdk0 | | dpdk1 | |
     |        | | | dpdk0 | | dpdk1 | | |        |       | +-------+ +-------+ |
     |        | | +---+---+ +---+---+ | |        |       |        host2        |
     |        | +-----|---------|-----+ |        |       +---------------------+
     |        |       |         |       |        |
     |        |     +-+---------+-+     |        |
     |        |     | test_patch  |     |        |
     |        |     +------|------+     |        |
     |        +------------|------------+        |
     |                     |                     |
     | +-------------------|-------------------+ |
     | |            +------+------+            | |
     | |         +--| bond_patch  ---+         | |
     | |         |  +-------------+  |         | |
     | |         |                   |         | |
     | | +-------+--------+ +--------+-------+ | |
     | | | dpdkvhostuser0 | | dpdkvhostuser1 | | |
     | | +-------+--------+ +--------+-------+ | |
     | +---------|-------------------|---------+ |
     |           |   +---------+     |           |
     |           +---+ testPMD +-----+           |
     |               +---------+                 |
     |                  host1                    |
     +-------------------------------------------+

    The recipe provides additional recipe parameters to configure the bonding
    device.

        :param bonding_mode:
            (mandatory test parameter) the bonding mode to be configured on
            the dpdkbond device.
        :param lacp_mode:
            (mandatory test parameter) the lacp mode to be configured
            on the dpdkbond device.
        :param dpdk_lcore_mask:
            (mandatory test parameter) cores to be used for the DPDK in OVS
        :param pmd_cpu_mask:
            (mandatory test parameter) cores to be used for the PMD in OVS
        :param trex_dpdk_cores:
            (mandatory test parameter) cores to be used by the Trex generator
        :param trex_dor:
            (mandatory test parameter) path to the Trex directory

    No subconfiguration are applied through Mixin classes as they are not
    applicable for this scenario. Subconfiguration for Open vSwitch is included
    via :any:`ovs_dpdk_bridge_configuration` method.

    The actual test machinery is implemented in the :any:`BaseEnrtRecipe` class.
    """
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))
    host1.eth1 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))
    host2.eth1 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    net1_ipv4 = IPv4NetworkParam(default="192.168.101.0/24")
    net1_ipv6 = IPv6NetworkParam(default="fc00::/64")
    net2_ipv4 = IPv4NetworkParam(default="192.168.102.0/24")
    net2_ipv6 = IPv6NetworkParam(default="fd00::/64")

    bonding_mode = StrParam(mandatory=True)
    lacp_mode = StrParam(mandatory=True)

    hugepages = IntParam(default=12)
    dpdk_socket_mem = IntParam(default=1024)
    dpdk_lcore_mask = StrParam(mandatory=True)
    pmd_cpu_mask = StrParam(mandatory=True)

    testpmd_cores = StrParam(mandatory=True)
    testpmd_dpdk_cores = StrParam(mandatory=True)

    trex_dpdk_cores = StrParam(mandatory=True)
    trex_dir = StrParam(mandatory=True)

    perf_duration = IntParam(default=60)
    perf_iterations = IntParam(default=5)
    perf_msg_size = IntParam(default=64)

    cpu_perf_tool = Param(default=StatCPUMeasurement)
    net_perf_tool = Param(default=TRexFlowMeasurement)

    def test_wide_configuration(self):
        """
        Test wide configuration for this recipe involves adding an IPv4 and
        IPv6 address to the matched eth0 and eth1 nics on both hosts.

        | host1.eth0 = 192.168.101.1/24 and fc00::1/64
        | host1.eth1 = 192.168.102.1/24 and fd00::1/64

        | host2.eth0 = 192.168.101.2/24 and fc00::2/64
        | host2.eth1 = 192.168.102.2/24 and fd00::2/64

        Both hosts are configured to allocate 1G hugepages and their testing
        nics drivers are overriden to use vfio-pci driver.

        Host1 is configured to accomodate OvS DPDK specific bonding setup and
        launches an instance of the TestPMD application to reflect traffic that
        arrives to the OvS bridge of the host.

        """
        host1, host2 = self.matched.host1, self.matched.host2

        ipv4_addr1 = interface_addresses(self.params.net1_ipv4)
        ipv6_addr1 = interface_addresses(self.params.net1_ipv6)

        ipv4_addr2 = interface_addresses(self.params.net2_ipv4)
        ipv6_addr2 = interface_addresses(self.params.net2_ipv6)

        for i, host in enumerate([host1, host2]):
            host.dummy_cfg = DummyRecipeConfig(
                eth0=DummyEthDevice(host.eth0.bus_info, host.eth0.hwaddr, _id="eth" + str(i),
                                    ips=[next(ipv4_addr1), next(ipv6_addr1)]
                                    ),
                eth1=DummyEthDevice(host.eth1.bus_info, host.eth1.hwaddr, _id="eth" + str(i + 1),
                                    ips=[next(ipv4_addr2), next(ipv6_addr2)]
                                    ),

                netns=host,
                testpmd=None
            )

            host.run(f"echo -n {self.params.hugepages} /sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages")
            host.run("modprobe vfio-pci")

            host.run(f"driverctl set-override {host.dummy_cfg.eth0.bus_info} vfio-pci")
            host.run(f"driverctl set-override {host.dummy_cfg.eth1.bus_info} vfio-pci")

        self.ovs_dpdk_bridge_configuration(host1)

        host1.dummy_cfg.testpmd = host1.run(
            TestPMD(
                coremask=self.params.testpmd_cores,
                pmd_coremask=self.params.testpmd_dpdk_cores,
                forward_mode="macswap",
                nics=["vhost0", "vhost1"]),
            bg=True)

        configuration = super().test_wide_configuration()
        return configuration

    def ovs_dpdk_bridge_configuration(self, host):
        """
        Host has an OvS setup with 2 bridges interconnected with patch ports.
        First bridge, called "bond_bridge", configures dpdkbond that uses 2 dpdk interfaces.
        Second bridge, called "test_bridge", configures 2 dpdkvhostuser ports.
        Finally, both bridges have their flows deleted and set to "NORMAL" action.
        """
        host.run("systemctl enable openvswitch")
        host.run("systemctl start openvswitch")
        host.run(f"ovs-vsctl --no-wait set Open_vSwitch . other_config:dpdk-socket-mem="
                 f"{self.params.dpdk_socket_mem}")
        host.run(f"ovs-vsctl --no-wait set Open_vSwitch . other_config:dpdk-lcore-mask="
                 f"{self.params.dpdk_lcore_mask}")
        host.run(f"ovs-vsctl --no-wait set Open_vSwitch . other_config:pmd-cpu-mask="
                 f"{self.params.pmd_cpu_mask}")
        host.run("ovs-vsctl --no-wait set Open_vSwitch . other_config:dpdk-init=true")

        host.run(f"ovs-vsctl add-br {host.dummy_cfg.bond_br} "
                 f"-- set bridge {host.dummy_cfg.bond_br} datapath_type=netdev")

        host.run(f"ovs-vsctl add-bond {host.dummy_cfg.bond_br} dpdkbond dpdk0 dpdk1 "
                 f"bond_mode={self.params.bonding_mode} lacp={self.params.lacp_mode} "
                 f"-- set Interface dpdk0 type=dpdk options:dpdk-devargs={host.dummy_cfg.eth0.bus_info} "
                 f"-- set Interface dpdk1 type=dpdk options:dpdk-devargs={host.dummy_cfg.eth1.bus_info}")

        host.run(f"ovs-vsctl add-br {host.dummy_cfg.test_br} "
                 f"-- set bridge {host.dummy_cfg.test_br} datapath_type=netdev")

        host.run(f"ovs-vsctl add-port {host.dummy_cfg.test_br} vhost0 "
                 f"-- set Interface vhost0 type=dpdkvhostuser")
        host.run(f"ovs-vsctl add-port {host.dummy_cfg.test_br} vhost1 "
                 f"-- set Interface vhost1 type=dpdkvhostuser")

        host.run(f"ovs-vsctl -- add-port {host.dummy_cfg.test_br} bond_patch "
                 "-- set interface bond_patch type=patch options:peer=test_patch "
                 f"-- add-port {host.dummy_cfg.bond_br} test_patch "
                 "-- set interface test_patch type=patch options:peer=bond_patch")

        host.run(f"ovs-ofctl mod-port {host.dummy_cfg.bond_br} dpdk0 up")
        host.run(f"ovs-ofctl mod-port {host.dummy_cfg.bond_br} dpdk1 up")

        for bridge in (host.dummy_cfg.test_br, host.dummy_cfg.bond_br):
            host.run(f"ip l set {bridge} up")
            host.run(f"ovs-ofctl del-flows {bridge}")
            host.run(f"ovs-ofctl add-flow {bridge} actions=NORMAL")

    def generate_perf_configurations(self, config):
        """
        OvSDPDKBondRecipe perf test configuration generator.

        OvSDPDKBondRecipe requires a specific TrexFlowMeasurement
        configuration, where it needs additional parameters,
        therefore it overrides the inherited method
        from the :any:`BaseEnrtRecipe`.

        The generator creates and loops over all flow combinations
        between the hosts to measure the performance.
        In addition to that during each flow combination measurement,
        we add CPU utilization measurement to run in the background.

        Finally for each generated perf test configuration we register
        measurement evaluators based on the :any:`cpu_perf_evaluators` and
        :any:`net_perf_evaluators` properties.

        :return: Perf test configuration
        :rtype: :any:`PerfRecipeConf`
        """
        host1, host2 = self.matched.host1, self.matched.host2
        testpmd_nics = [host1.dummy_cfg.eth0, host1.dummy_cfg.eth1]
        trex_nics = [host2.dummy_cfg.eth0, host2.dummy_cfg.eth1]
        flows = []
        for trex_nic, testpmd_nic in zip(trex_nics, testpmd_nics):
            trex_bind = dict(mac_addr=trex_nic.hwaddr,
                             pci_addr=trex_nic.bus_info,
                             ip_addr=trex_nic.ips[0],
                             family=trex_nic.ips[0].family)
            testpmd_bind = dict(mac_addr=testpmd_nic.hwaddr,
                                pci_addr=testpmd_nic.bus_info,
                                ip_addr=testpmd_nic.ips[0],
                                family=testpmd_nic.ips[0].family)
            flows.append(PerfFlow(
                type="UDPMultiflow",
                generator=host2,
                generator_nic=trex_nic,
                generator_bind=trex_bind,
                receiver=host1,
                receiver_nic=testpmd_nic,
                receiver_bind=testpmd_bind,
                msg_size=self.params.perf_msg_size,
                duration=self.params.perf_duration,
                parallel_streams=1,
                cpupin=None))

        perf_recipe_conf = dict(
            recipe_config=config,
            flows=flows,
        )

        cpu_measurement = self.params.cpu_perf_tool([host1, host2],
                                                    perf_recipe_conf)

        flows_measurement = TRexFlowMeasurement(
            flows,
            self.params.trex_dir,
            self.params.trex_dpdk_cores.split(","),
            perf_recipe_conf,
        )
        perf_conf = PerfRecipeConf(
            measurements=[
                cpu_measurement,
                flows_measurement,
            ],
            iterations=self.params.perf_iterations,
        )
        perf_conf.register_evaluators(cpu_measurement, self.cpu_perf_evaluators)
        perf_conf.register_evaluators(flows_measurement, self.net_perf_evaluators)
        return perf_conf

    def do_perf_tests(self, recipe_config):
        """
        OvSDPDKBondRecipe overrides inherited :any:`do_perf_tests` method,
        due to having its own :any:`generate_perf_configurations`, which returns
        only a single :any:`PerfRecipeConf` instead of a list.
        PerfRecipe methods are used to execute, report and evaluate the results.
        """
        perf_config = self.generate_perf_configurations(recipe_config)
        result = self.perf_test(perf_config)
        self.perf_report_and_evaluate(result)

    def generate_test_wide_description(self, config):
        """
        Test wide description is extended with the bus info of the configured interfaces
        used for the DPDK purposes.
        Description is further expanded upon wit the OvS configuration on the host,
        containing names of the newly created bridges and intefaces, bonding mode and lacp mode
        of the dpdkbond interface, as well as patch ports used for the connection of the bridges.
        Lastly, configuration of the TestPMD instance is appended.
        """
        desc = super().generate_test_wide_description(config)
        host1, host2 = self.matched.host1, self.matched.host2
        for i, host in enumerate([host1, host2]):
            desc += [f"Configured host{i} interfaces with bus info: {host.dummy_cfg.eth0.bus_info} "
                     f"and {host.dummy_cfg.eth1.bus_info} to be controlled by vfio-pci"]

        desc += [
            f"Created OvS bridges: {host1.dummy_cfg.test_br} and {host1.dummy_cfg.bond_br} on host1 "
            f"set with datapath_type to netdev",
            f"Created dpdkbond on {host1.dummy_cfg.bond_br} with bonding_mode set to "
            f"{self.params.bonding_mode} using lacp_mode set to "
            f"{self.params.lacp_mode}",
            f"Interconnected OvS bridges with patch ports: test_patch and bond_patch",
            f"Deleted all flows on both bridges and created a new one with \"actions=NORMAL\"",
            f"TestPMD in a forward-mode macswap started on the host1 {host1.dummy_cfg.test_br} vhost0 port"]

        return desc

    def test_wide_deconfiguration(self, config):
        """
        Test wide deconfiguration consists of killing a TestPMD instance created in the setup,
        removal of the bridges and process of returning the control of interfaces to the kernel drivers.
        However, driverctl utility can get stuck due to the bug in the openvswitch, thus a simple
        restart of the service is used to free the handles and resume the driverctl utility's job.
        """
        host1, host2 = self.matched.host1, self.matched.host2

        testpmd = host1.dummy_cfg.testpmd
        if testpmd:
            testpmd.kill(signal.SIGINT)
            testpmd.wait()

        host1.run(f"ovs-vsctl del-br {host1.dummy_cfg.test_br}")
        host1.run(f"ovs-vsctl del-br {host1.dummy_cfg.bond_br}")

        host1.run(f"driverctl unset-override {host1.dummy_cfg.eth0.bus_info} & sleep 1; systemctl restart openvswitch")
        host1.run(f"driverctl unset-override {host1.dummy_cfg.eth1.bus_info} & sleep 1; systemctl restart openvswitch")

        host2.run(f"driverctl unset-override {host2.dummy_cfg.eth0.bus_info}")
        host2.run(f"driverctl unset-override {host2.dummy_cfg.eth1.bus_info}")

    def generate_ping_endpoints(self, config):
        return []

    def generate_perf_endpoints(self, config):
        return [(self.matched.host1.dummy_cfg, self.matched.host2.dummy_cfg)]

    def apply_perf_test_tweak(self, config):
        pass

    def describe_perf_test_tweak(self, config):
        pass

    def remove_perf_test_tweak(self, config):
        pass
