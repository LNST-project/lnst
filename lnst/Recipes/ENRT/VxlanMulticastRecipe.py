"""
Implements scenario similar to regression_tests/phase3/
(vxlan_multicast.xml + vxlan_multicast.py)
"""
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Devices import BridgeDevice, VxlanDevice

class VxlanMulticastRecipe(BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))
    host1.tap0 = DeviceReq(label="to_guest1")

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    guest1 = HostReq()
    guest1.eth0 = DeviceReq(label="to_guest1")

    def test_wide_configuration(self):
        host1, host2, guest1 = self.matched.host1, self.matched.host2, self.matched.guest1

        for machine in [host1, host2, guest1]:
            machine.eth0.down()
        host1.tap0.down()

        net_addr = "192.168.0"
        vxlan_net_addr = "192.168.100"
        vxlan_net_addr6 = "fc00:0:0:0"
        #TODO: Enable usage of a proper address (like 239.1.1.1)
        vxlan_group_ip = "192.168.0.3"

        host1.br0 = BridgeDevice()
        host1.br0.slave_add(host1.eth0)
        host1.br0.slave_add(host1.tap0)

        for i, (machine, dev) in enumerate([(host1, host1.br0), (guest1, guest1.eth0),
                                            (host2, host2.eth0)]):
            dev.ip_add(ipaddress(net_addr + "." + str(i+1) + "/24"))
            machine.vxlan0 = VxlanDevice(vxlan_id='1', group=vxlan_group_ip)
            machine.vxlan0.realdev = dev
            machine.vxlan0.ip_add(ipaddress(vxlan_net_addr + "." + str (i+1) + "/24"))
            machine.vxlan0.ip_add(ipaddress(vxlan_net_addr6 + "::" + str (i+1) + "/64"))

        #Due to limitations in the current EnrtConfiguration
        #class, a single vlan test pair is chosen
        configuration = EnrtConfiguration()
        configuration.endpoint1 = host1.vxlan0
        configuration.endpoint2 = host2.vxlan0

        if "mtu" in self.params:
            for machine in [host1, host2, guest1]:
                machine.vxlan0.mtu = self.params.mtu

        for machine in [host1, host2, guest1]:
            machine.eth0.up()
        host1.tap0.up()
        host1.br0.up()
        for machine in [host1, host2, guest1]:
            machine.vxlan0.up()

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for host in [host1, host2]:
                host.run("service irqbalance stop")
                self._pin_dev_interrupts(host.eth0, self.params.dev_intr_cpu)

        if self.params.perf_parallel_streams > 1:
            for host in [host1, host2]:
                host.run("tc qdisc replace dev %s root mq" % host.eth0.name)

        return configuration

    def test_wide_deconfiguration(self, config):
        host1, host2, guest1 = self.matched.host1, self.matched.host2, self.matched.guest1

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for host in [host1, host2]:
                host.run("service irqbalance start")
