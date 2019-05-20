"""
Implements scenario similar to regression_tests/phase3/
(2_virt_ovs_vxlan.xml + 2_virt_ovs_vxlan.py)
"""
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Devices import OvsBridgeDevice

class VirtOvsVxlanRecipe(BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))
    host1.tap0 = DeviceReq(label="to_guest1")
    host1.tap1 = DeviceReq(label="to_guest2")

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))
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

    def test_wide_configuration(self):
        host1, host2, guest1, guest2, guest3, guest4 = self.matched.host1, self.matched.host2,\
            self.matched.guest1, self.matched.guest2, self.matched.guest3, self.matched.guest4

        for host in [host1, host2]:
            host.eth0.down()
            host.tap0.down()
            host.tap1.down()
        for guest in [guest1, guest2, guest3, guest4]:
            guest.eth0.down()

        net_addr = "192.168.2"
        vxlan_net_addr = "192.168.100"
        vxlan_net_addr6 = "fc00:0:0:0"

        flow_entries=[]
        flow_entries.append("table=0,in_port=5,actions=set_field:100->tun_id,output:10")
        flow_entries.append("table=0,in_port=6,actions=set_field:200->tun_id,output:10")
        flow_entries.append("table=0,in_port=10,tun_id=100,actions=output:5")
        flow_entries.append("table=0,in_port=10,tun_id=200,actions=output:6")
        flow_entries.append("table=0,priority=100,actions=drop")

        for i, host in enumerate([host1, host2]):
            host.eth0.ip_add(ipaddress(net_addr + "." + str (i+1) + "/24"))
            host.br0 = OvsBridgeDevice()
            for dev, ofport_r in [(host.tap0, '5'), (host.tap1, '6')]:
                host.br0.port_add(dev, set_iface=True, ofport_request=ofport_r)
            tunnel_opts = {"option:remote_ip" : net_addr + "." + str (2-i), "option:key" : "flow",
                           "ofport_request" : '10'}
            host.br0.tunnel_add("vxlan", tunnel_opts)
            host.br0.flows_add(flow_entries)

        for i, guest in enumerate([guest1, guest2, guest3, guest4]):
            guest.eth0.ip_add(ipaddress(vxlan_net_addr + "." + str (i+1) + "/24"))
            guest.eth0.ip_add(ipaddress(vxlan_net_addr6 + "::" + str (i+1) + "/64"))

        #Due to limitations in the current EnrtConfiguration
        #class, a single vlan test pair is chosen
        configuration = EnrtConfiguration()
        configuration.endpoint1 = guest1.eth0
        configuration.endpoint2 = guest3.eth0

        if "mtu" in self.params:
            for guest in [guest1, guest2, guest3, guest4]:
                guest.eth0.mtu = self.params.mtu

        for host in [host1, host2]:
            host.eth0.up()
            host.tap0.up()
            host.tap1.up()
            host.br0.up()
        for guest in [guest1, guest2, guest3, guest4]:
            guest.eth0.up()

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for machine in [host1, host2, guest1, guest2, guest3, guest4]:
                machine.run("service irqbalance stop")
            for host in [host1, host2]:
                self._pin_dev_interrupts(host.eth0, self.params.dev_intr_cpu)

        if self.params.perf_parallel_streams > 1:
            for host in [host1, host2]:
                host.run("tc qdisc replace dev %s root mq" % host.eth0.name)

        return configuration

    def test_wide_deconfiguration(self, config):
        host1, host2, guest1, guest2, guest3, guest4 = self.matched.host1, self.matched.host2,\
            self.matched.guest1, self.matched.guest2, self.matched.guest3, self.matched.guest4

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for machine in [host1, host2, guest1, guest2, guest3, guest4]:
                machine.run("service irqbalance start")
