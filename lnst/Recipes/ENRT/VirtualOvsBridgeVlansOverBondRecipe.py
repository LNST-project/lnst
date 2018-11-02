"""
Implements scenario similar to regression_tests/phase2/
(virtual_ovs_bridge_2_vlans_over_active_backup_bond.xml +
virtual_ovs_bridge_2_vlans_over_active_backup_bond.py
)
"""
from lnst.Common.Parameters import Param, IntParam, StrParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Devices import VlanDevice
from lnst.Devices import OvsBridgeDevice

class VirtualOvsBridgeVlansOverBondRecipe(BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth1 = DeviceReq(label="to_switch")
    host1.eth2 = DeviceReq(label="to_switch")
    host1.tap0 = DeviceReq(label="to_guest1")
    host1.tap1 = DeviceReq(label="to_guest2")

    host2 = HostReq()
    host2.eth1 = DeviceReq(label="to_switch")
    host2.eth2 = DeviceReq(label="to_switch")
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

    bonding_mode = StrParam(mandatory = True)
    miimon_value = IntParam(mandatory = True)

    def test_wide_configuration(self):
        host1, host2, guest1, guest2, guest3, guest4 = self.matched.host1, self.matched.host2, self.matched.guest1, self.matched.guest2, self.matched.guest3, self.matched.guest4

        host1.eth1.down()
        host1.eth2.down()
        host1.tap0.down()
        host1.tap1.down()
        host1.br0 = OvsBridgeDevice()
        for d, tag in [(host1.tap0, "10"), (host1.tap1, "20")]:
            host1.br0.port_add(d, tag=tag)

        #miimon cannot be set due to colon in argument name --> other_config:bond-miimon-interval
        #https://access.redhat.com/documentation/en-us/red_hat_openstack_platform/12/html/advanced_overcloud_customization/appe-bonding_options
        host1.br0.bond_add("bond_host1", (host1.eth1, host1.eth2), bond_mode=self.params.bonding_mode)

        host2.eth1.down()
        host2.eth2.down()
        host2.tap0.down()
        host2.tap1.down()
        host2.br0 = OvsBridgeDevice()

        for d, tag in [(host2.tap0, "10"), (host2.tap1, "20")]:
            host2.br0.port_add(d, tag=tag)

        host2.br0.bond_add("bond_host2", (host2.eth1, host2.eth2), bond_mode=self.params.bonding_mode)

        guest1.eth0.down()

        guest2.eth0.down()

        guest3.eth0.down()

        guest4.eth0.down()

        #Due to limitations in the current EnrtConfiguration
        #class, a single vlan test pair is chosen
        configuration = EnrtConfiguration()
        configuration.endpoint1 = guest1.eth0
        configuration.endpoint2 = guest3.eth0

        if "mtu" in self.params:
            host1.br0.mtu = self.params.mtu
            host2.br0.mtu = self.params.mtu
            guest1.eth0.mtu = self.params.mtu
            guest2.eth0.mtu = self.params.mtu
            guest3.eth0.mtu = self.params.mtu
            guest4.eth0.mtu = self.params.mtu

        net_addr_1 = "192.168.10"
        net_addr6_1 = "fc00:0:0:1"
        net_addr_2 = "192.168.20"
        net_addr6_2 = "fc00:0:0:2"

        for i, m in enumerate([guest1, guest3]):
            m.eth0.ip_add(ipaddress(net_addr_1 + "." + str (i+1) + "/24"))
            m.eth0.ip_add(ipaddress(net_addr6_1 + "::" + str (i+1) + "/64"))

        for i, m in enumerate([guest2, guest4]):
            m.eth0.ip_add(ipaddress(net_addr_2 + "." + str (i+1) + "/24"))
            m.eth0.ip_add(ipaddress(net_addr6_2 + "::" + str (i+1) + "/64"))

        host1.eth1.up()
        host1.eth2.up()
        host1.tap0.up()
        host1.tap1.up()
        host1.br0.up()
        host2.eth1.up()
        host2.eth2.up()
        host2.tap0.up()
        host2.tap1.up()
        host2.br0.up()
        guest1.eth0.up()
        guest2.eth0.up()
        guest3.eth0.up()
        guest4.eth0.up()

        #TODO better service handling through HostAPI
        host1.run("service irqbalance stop")
        host2.run("service irqbalance stop")
        guest1.run("service irqbalance stop")
        guest2.run("service irqbalance stop")
        guest3.run("service irqbalance stop")
        guest4.run("service irqbalance stop")

        for m in self.matched:
            for dev in m.devices:
                self._pin_dev_interrupts(dev, self.params.dev_intr_cpu)

        return configuration

    def test_wide_deconfiguration(self, config):
        host1, host2, guest1, guest2, guest3, guest4 = self.matched.host1, self.matched.host2, self.matched.guest1, self.matched.guest2, self.matched.guest3, self.matched.guest4

        #TODO better service handling through HostAPI
        host1.run("service irqbalance start")
        host2.run("service irqbalance start")
        guest1.run("service irqbalance start")
        guest2.run("service irqbalance start")
        guest3.run("service irqbalance start")
        guest4.run("service irqbalance start")
