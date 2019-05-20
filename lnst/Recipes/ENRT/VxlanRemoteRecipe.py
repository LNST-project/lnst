"""
Implements scenario similar to regression_tests/phase3/
(vxlan_remote.xml + vxlan_remote.py)
"""
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Devices import VxlanDevice

class VxlanRemoteRecipe(BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    def test_wide_configuration(self):
        host1, host2 = self.matched.host1, self.matched.host2

        for host in [host1, host2]:
            host.eth0.down()

        net_addr = "192.168.0"
        vxlan_net_addr = "192.168.100"
        vxlan_net_addr6 = "fc00:0:0:0"

        for i, host in enumerate([host1, host2]):
            host.eth0.ip_add(ipaddress(net_addr + "." + str(i+1) + "/24"))
            host.vxlan0 = VxlanDevice(vxlan_id='1', remote=net_addr + "." + str(2-i))
            host.vxlan0.realdev = host.eth0
            host.vxlan0.ip_add(ipaddress(vxlan_net_addr + "." + str (i+1) + "/24"))
            host.vxlan0.ip_add(ipaddress(vxlan_net_addr6 + "::" + str (i+1) + "/64"))

        #Due to limitations in the current EnrtConfiguration
        #class, a single vlan test pair is chosen
        configuration = EnrtConfiguration()
        configuration.endpoint1 = host1.vxlan0
        configuration.endpoint2 = host2.vxlan0

        if "mtu" in self.params:
            for host in [host1, host2]:
                host.vxlan0.mtu = self.params.mtu

        for host in [host1, host2]:
            host.eth0.up()
            host.vxlan0.up()

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
        host1, host2 = self.matched.host1, self.matched.host2

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for host in [host1, host2]:
                host.run("service irqbalance start")
