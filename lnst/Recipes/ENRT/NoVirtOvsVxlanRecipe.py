"""
Implements scenario similar to regression_tests/phase3/
(novirt_ovs_vxlan.xml + novirt_ovs_vxlan.py)
"""
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Devices import OvsBridgeDevice

class NoVirtOvsVxlanRecipe(BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    def test_wide_configuration(self):
        host1, host2 = self.matched.host1, self.matched.host2

        for host in [host1, host2]:
            host.eth0.down()

        net_addr = "192.168.2"
        vxlan_net_addr = "192.168.100"
        vxlan_net_addr6 = "fc00:0:0:0"

        flow_entries=[]
        flow_entries.append("table=0,in_port=5,actions=set_field:100->tun_id,output:10")
        flow_entries.append("table=0,in_port=10,tun_id=100,actions=output:5")
        flow_entries.append("table=0,priority=100,actions=drop")

        for i, host in enumerate([host1, host2]):
            host.eth0.ip_add(ipaddress(net_addr + "." + str (i+1) + "/24"))
            host.br0 = OvsBridgeDevice()
            host.int0 = host.br0.internal_port_add(ofport_request='5', name="int0")
            host.int0.ip_add(ipaddress(vxlan_net_addr + "." + str (i+1) + "/24"))
            host.int0.ip_add(ipaddress(vxlan_net_addr6 + "::" + str (i+1) + "/64"))
            tunnel_opts = {"option:remote_ip" : net_addr + "." + str (2-i), "option:key" : "flow",
                           "ofport_request" : "10"}
            host.br0.tunnel_add("vxlan", tunnel_opts)
            host.br0.flows_add(flow_entries)

        #Due to limitations in the current EnrtConfiguration
        #class, a single vlan test pair is chosen
        configuration = EnrtConfiguration()
        configuration.endpoint1 = host1.int0
        configuration.endpoint2 = host2.int0

        if "mtu" in self.params:
            for host in [host1, host2]:
                host.int0.mtu = self.params.mtu

        for host in [host1, host2]:
            host.eth0.up()
            host.int0.up()
            host.br0.up()

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
