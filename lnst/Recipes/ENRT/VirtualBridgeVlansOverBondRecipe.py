"""
Implements scenario similar to regression_tests/phase1/
(virtual_bridge_2_vlans_over_active_backup_bond.xml + virtual_bridge_2_vlans_over_bond.py)
"""
from lnst.Common.Parameters import Param, IntParam, StrParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Devices import VlanDevice
from lnst.Devices import BondDevice
from lnst.Devices import BridgeDevice
from lnst.Common.LnstError import LnstError

class VirtualBridgeVlansOverBondRecipe(BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch")
    host1.eth1 = DeviceReq(label="to_switch")
    host1.tap0 = DeviceReq(label="to_guest1")
    host1.tap1 = DeviceReq(label="to_guest2")

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch")
    host2.eth1 = DeviceReq(label="to_switch")
    host2.tap0 = DeviceReq(label="to_guest3")
    host2.tap1 = DeviceReq(label="to_guest4")

    guest1 = HostReq()
    guest1.eth0 = DeviceReq(label="to_guest1")

    guest2 = HostReq()
    guest2.eth0 = DeviceReq(label="to_guest2")

    guest3 = HostReq()
    guest3.eth0 = DeviceReq(label="to_guest3")

    guest4 = HostReq()
    guest4.eth0 = DeviceReq(label="to_guest4")

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on"),
        dict(gro="off", gso="on", tso="on", tx="on"),
        dict(gro="on", gso="off", tso="off", tx="on"),
        dict(gro="on", gso="on", tso="off", tx="off")))

    bonding_mode = StrParam(mandatory=True)
    miimon_value = IntParam(mandatory=True)

    def test_wide_configuration(self):
        host1, host2, guest1, guest2, guest3, guest4 = self.matched.host1, self.matched.host2, self.matched.guest1, self.matched.guest2, self.matched.guest3, self.matched.guest4

        for host in [host1, host2]:
            host.eth0.down()
            host.eth1.down()
            host.tap0.down()
            host.tap1.down()
            host.bond0 = BondDevice(mode=self.params.bonding_mode, miimon=self.params.miimon_value)
            host.bond0.slave_add(host.eth0)
            host.bond0.slave_add(host.eth1)
            host.br0 = BridgeDevice()
            host.br0.slave_add(host.tap0)
            host.br1 = BridgeDevice()
            host.br1.slave_add(host.tap1)

        for guest in (guest1, guest2, guest3, guest4):
            guest.eth0.down()

        host1_vlan_args0 = dict(realdev=host1.bond0, vlan_id=10, master=host1.br0)
        host1_vlan_args1 = dict(realdev=host1.bond0, vlan_id=20, master=host1.br1)
        host2_vlan_args0 = dict(realdev=host2.bond0, vlan_id=10, master=host2.br0)
        host2_vlan_args1 = dict(realdev=host2.bond0, vlan_id=20, master=host2.br1)
        if "mtu" in self.params:
            for host in [host1, host2]:
                host1.bond0.mtu = self.params.mtu
                host1.tap0.mtu = self.params.mtu
                host1.tap1.mtu = self.params.mtu
                host1.br0.mtu = self.params.mtu
                host1.br1.mtu = self.params.mtu
            for guest in [guest1, guest2, guest3, guest4]:
                guest.eth0.mtu = self.params.mtu
            for vlan_args in (host1_vlan_args0, host1_vlan_args1,
                              host2_vlan_args0, host2_vlan_args1):
                vlan_args["mtu"] = self.params.mtu

        host1.vlan0 = VlanDevice(**host1_vlan_args0)
        host1.vlan1 = VlanDevice(**host1_vlan_args1)
        host2.vlan0 = VlanDevice(**host2_vlan_args0)
        host2.vlan1 = VlanDevice(**host2_vlan_args1)

        #Due to limitations in the current EnrtConfiguration
        #class, a single vlan test pair is chosen
        configuration = EnrtConfiguration()
        configuration.endpoint1 = guest1.eth0
        configuration.endpoint2 = guest3.eth0

        net_addr_1 = "192.168.10"
        net_addr_2 = "192.168.20"
        net_addr6_1 = "fc00:0:0:1"
        net_addr6_2 = "fc00:0:0:2"

        for host, (guest_a, guest_b), n in [(host1, (guest1, guest2), 1), (host2, (guest3, guest4), 3)]:
            host.bond0.ip_add(ipaddress("1.2.3.4"))
            host.br0.ip_add(ipaddress(net_addr_1 + "." + str(n) + "/24"))
            host.br1.ip_add(ipaddress(net_addr_2 + "." + str(n) + "/24"))
            guest_a.eth0.ip_add(ipaddress(net_addr_1 + "." + str(n+1) + "/24"))
            guest_a.eth0.ip_add(ipaddress(net_addr6_1 + "::" + str(n+1) + "/64"))
            guest_b.eth0.ip_add(ipaddress(net_addr_2 + "." + str(n+1) + "/24"))
            guest_b.eth0.ip_add(ipaddress(net_addr6_2 + "::" + str(n+1) + "/64"))

        for host, guest_a, guest_b in [(host1, guest1, guest2), (host2, guest3, guest4)]:
            host.eth0.up()
            host.eth1.up()
            host.tap0.up()
            host.tap1.up()
            host.bond0.up()
            host.vlan0.up()
            host.vlan1.up()
            host.br0.up()
            host.br1.up()
            guest_a.eth0.up()
            guest_b.eth0.up()

        #TODO better service handling through HostAPI
        if "perf_tool_cpu" in self.params:
            raise LnstError("'perf_tool_cpu' (%d) should not be set for this test" % self.params.perf_tool_cpu)

        if "dev_intr_cpu" in self.params:
            for host in [host1, host2]:
                host.run("service irqbalance stop")
                for dev in [host.eth0, host.eth1]:
                    self._pin_dev_interrupts(dev, self.params.dev_intr_cpu)

        if self.params.perf_parallel_streams > 1:
            for host in [host1, host2]:
                for dev in [host.eth0, host.eth1]:
                    host.run("tc qdisc replace dev %s root mq" % dev.name)

        return configuration

    def test_wide_deconfiguration(self, config):
        host1, host2, guest1, guest2, guest3, guest4 = self.matched.host1, self.matched.host2, self.matched.guest1, self.matched.guest2, self.matched.guest3, self.matched.guest4

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for host in [host1, host2]:
                host.run("service irqbalance start")
