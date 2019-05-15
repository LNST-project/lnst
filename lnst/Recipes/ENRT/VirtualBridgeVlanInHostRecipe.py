"""
Implements scenario similar to regression_tests/phase1/
(virtual_bridge_vlan_in_host.xml + virtual_bridge_vlan_in_host.py)
"""
from lnst.Common.Parameters import Param
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Devices import VlanDevice
from lnst.Devices import BridgeDevice
from lnst.Common.LnstError import LnstError

class VirtualBridgeVlanInHostRecipe(BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))
    host1.tap0 = DeviceReq(label="to_guest")

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    guest1 = HostReq()
    guest1.eth0 = DeviceReq(label="to_guest")

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="off", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="on", gso="off", tso="off", tx="on", rx="on"),
        dict(gro="on", gso="on", tso="off", tx="off", rx="on"),
        dict(gro="on", gso="on", tso="on", tx="on", rx="off")))

    def test_wide_configuration(self):
        host1, host2, guest1 = self.matched.host1, self.matched.host2, self.matched.guest1

        host1.eth0.down()
        host1.tap0.down()
        host1.br0 = BridgeDevice()
        host1.br0.slave_add(host1.tap0)

        host2.eth0.down()

        guest1.eth0.down()

        host1_vlan_args0 = dict(realdev=host1.eth0, vlan_id=10, master=host1.br0)
        host2_vlan_args0 = dict(realdev=host2.eth0, vlan_id=10)
        if "mtu" in self.params:
            host1.eth0.mtu = self.params.mtu
            host1.tap0.mtu = self.params.mtu
            host1.br0.mtu = self.params.mtu
            host2.eth0.mtu = self.params.mtu
            guest1.eth0.mtu = self.params.mtu
            for vlan_args in (host1_vlan_args0, host2_vlan_args0):
                vlan_args["mtu"] = self.params.mtu

        host1.vlan0 = VlanDevice(**host1_vlan_args0)
        host2.vlan0 = VlanDevice(**host2_vlan_args0)

        configuration = EnrtConfiguration()
        configuration.endpoint1 = guest1.eth0
        configuration.endpoint2 = host2.vlan0

        net_addr_1 = "192.168.10"
        net_addr6_1 = "fc00:0:0:1"

        host1.br0.ip_add(ipaddress(net_addr_1 + ".1/24"))
        host2.vlan0.ip_add(ipaddress(net_addr_1 + ".2/24"))
        host2.vlan0.ip_add(ipaddress(net_addr6_1 + "::2/64"))
        guest1.eth0.ip_add(ipaddress(net_addr_1 + ".3/24"))
        guest1.eth0.ip_add(ipaddress(net_addr6_1 + "::3/64"))

        host1.eth0.up()
        host1.tap0.up()
        host1.vlan0.up()
        host1.br0.up()
        host2.eth0.up()
        host2.vlan0.up()
        guest1.eth0.up()

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            raise LnstError("'dev_intr_cpu' (%d) should not be set for this test" % self.params.dev_intr_cpu)

        if "perf_tool_cpu" in self.params:
            for host in [host1, host2]:
                host.run("service irqbalance stop")
                self._pin_dev_interrupts(host.eth0, 0)

        if self.params.perf_parallel_streams > 1:
            for host in [host1, host2]:
                host.run("tc qdisc replace dev %s root mq" % host.eth0.name)

        return configuration

    def test_wide_deconfiguration(self, config):
        host1, host2, guest1 = self.matched.host1, self.matched.host2, self.matched.guest1

        #TODO better service handling through HostAPI
        if "perf_tool_cpu" in self.params:
            for host in [host1, host2]:
                host.run("service irqbalance start")
