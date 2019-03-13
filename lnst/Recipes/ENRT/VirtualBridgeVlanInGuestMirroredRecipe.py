"""
Implements scenario similar to regression_tests/phase1/
(virtual_bridge_vlan_in_guest_mirrored.xml + virtual_bridge_vlan_in_guest_mirrored.py)
"""
from lnst.Common.Parameters import Param
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Devices import VlanDevice
from lnst.Devices import BridgeDevice
from lnst.Common.LnstError import LnstError

class VirtualBridgeVlanInGuestMirroredRecipe(BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch")
    host1.tap0 = DeviceReq(label="to_guest1")

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch")
    host2.tap0 = DeviceReq(label="to_guest2")

    guest1 = HostReq()
    guest1.eth0 = DeviceReq(label="to_guest1")

    guest2 = HostReq()
    guest2.eth0 = DeviceReq(label="to_guest2")

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="off", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="on", gso="off", tso="off", tx="on", rx="on"),
        dict(gro="on", gso="on", tso="off", tx="off", rx="on"),
        dict(gro="on", gso="on", tso="on", tx="on", rx="off")))

    def test_wide_configuration(self):
        host1, host2, guest1, guest2 = self.matched.host1, self.matched.host2, self.matched.guest1, self.matched.guest2

        host1.eth0.down()
        host1.tap0.down()
        host1.br0 = BridgeDevice()
        host1.br0.slave_add(host1.eth0)
        host1.br0.slave_add(host1.tap0)

        host2.eth0.down()
        host2.tap0.down()
        host2.br0 = BridgeDevice()
        host2.br0.slave_add(host2.eth0)
        host2.br0.slave_add(host2.tap0)

        guest1.eth0.down()
        guest1.vlan1 = VlanDevice(realdev=guest1.eth0, vlan_id=10)

        guest2.eth0.down()
        guest2.vlan1 = VlanDevice(realdev=guest2.eth0, vlan_id=10)

        #Due to limitations in the current EnrtConfiguration
        #class, a single vlan test pair is chosen
        configuration = EnrtConfiguration()
        configuration.endpoint1 = guest1.vlan1
        configuration.endpoint2 = guest2.vlan1

        if "mtu" in self.params:
            host1.eth0.mtu = self.params.mtu
            host1.tap0.mtu = self.params.mtu
            host2.eth0.mtu = self.params.mtu
            host2.tap0.mtu = self.params.mtu
            host1.br0.mtu = self.params.mtu
            host2.br0.mtu = self.params.mtu
            guest1.eth0.mtu = self.params.mtu
            guest2.eth0.mtu = self.params.mtu
            guest1.vlan1.mtu = self.params.mtu
            guest2.vlan1.mtu = self.params.mtu

        net_addr_1 = "192.168.10"
        net_addr6_1 = "fc00:0:0:1"

        host1.br0.ip_add(ipaddress(net_addr_1 + ".1/24"))
        host2.br0.ip_add(ipaddress(net_addr_1 + ".2/24"))
        guest1.vlan1.ip_add(ipaddress(net_addr_1 + ".3/24"))
        guest1.vlan1.ip_add(ipaddress(net_addr6_1 + "::3/64"))
        guest2.vlan1.ip_add(ipaddress(net_addr_1 + ".4/24"))
        guest2.vlan1.ip_add(ipaddress(net_addr6_1 + "::4/64"))

        host1.eth0.up()
        host1.tap0.up()
        host1.br0.up()
        host2.eth0.up()
        host2.tap0.up()
        host2.br0.up()
        guest1.eth0.up()
        guest1.vlan1.up()
        guest2.eth0.up()
        guest2.vlan1.up()

        #TODO better service handling through HostAPI
        if "perf_tool_cpu" in self.params:
            raise LnstError("'perf_tool_cpu' (%d) should not be set for this test" % self.params.perf_tool_cpu)

        if "dev_intr_cpu" in self.params:
            for m in [host1, host2]:
                m.run("service irqbalance stop")
                self._pin_dev_interrupts(m.eth0, self.params.dev_intr_cpu)

        if self.params.perf_parallel_streams > 1:
            for m in [host1, host2]:
                m.run("tc qdisc replace dev %s root mq" % m.eth0.name)

        return configuration

    def test_wide_deconfiguration(self, config):
        host1, host2, guest1, guest2 = self.matched.host1, self.matched.host2, self.matched.guest1, self.matched.guest2

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for m in [host1, host2]:
                m.run("service irqbalance start")
