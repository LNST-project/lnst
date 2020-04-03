from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Devices import OvsBridgeDevice

class NoVirtOvsVxlanRecipe(CommonHWSubConfigMixin, BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    def test_wide_configuration(self):
        host1, host2 = self.matched.host1, self.matched.host2

        net_addr = "192.168.2"
        vxlan_net_addr = "192.168.100"
        vxlan_net_addr6 = "fc00:0:0:0"

        flow_entries=[]
        flow_entries.append("table=0,in_port=5,actions=set_field:100->"
            "tun_id,output:10")
        flow_entries.append("table=0,in_port=10,tun_id=100,actions="
            "output:5")
        flow_entries.append("table=0,priority=100,actions=drop")

        for i, host in enumerate([host1, host2]):
            host.eth0.down()
            host.eth0.ip_add(ipaddress(net_addr + "." + str(i+1) + "/24"))
            host.br0 = OvsBridgeDevice()
            host.int0 = host.br0.port_add(
                    interface_options={
                        'type': 'internal',
                        'ofport_request': 5,
                        'name': 'int0'})
            host.int0.ip_add(ipaddress(vxlan_net_addr + "." + str(i+1) +
                "/24"))
            host.int0.ip_add(ipaddress(vxlan_net_addr6 + "::" + str(i+1) +
                "/64"))
            tunnel_opts = {"option:remote_ip" : net_addr + "." + str(2-i),
                "option:key" : "flow", "ofport_request" : "10"}
            host.br0.tunnel_add("vxlan", tunnel_opts)
            host.br0.flows_add(flow_entries)
            host.eth0.up()
            host.int0.up()
            host.br0.up()

        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = [host1.eth0, host1.int0,
            host2.eth0, host2.int0]

        self.wait_tentative_ips(configuration.test_wide_devices)

        return configuration

    def generate_test_wide_description(self, config):
        host1, host2 = self.matched.host1, self.matched.host2
        desc = super().generate_test_wide_description(config)
        desc += [
            "\n".join([
                "Configured {}.{}.ips = {}".format(
                    dev.host.hostid, dev.name, dev.ips
                )
                for dev in config.test_wide_devices
            ]),
            "\n".join([
                "Configured {}.{}.ports = {}".format(
                    dev.host.hostid, dev.name, dev.ports
                )
                for dev in [host1.br0, host2.br0]
            ]),
            "\n".join([
                "Configured {}.{}.tunnels = {}".format(
                    dev.host.hostid, dev.name, dev.tunnels
                )
                for dev in [host1.br0, host2.br0]
            ]),
            "\n".join([
                "Configured {}.{}.flows = {}".format(
                    dev.host.hostid, dev.name, dev.flows_str
                )
                for dev in [host1.br0, host2.br0]
            ])
        ]
        return desc

    def test_wide_deconfiguration(self, config):
        del config.test_wide_devices

        super().test_wide_deconfiguration(config)

    def generate_ping_endpoints(self, config):
        return [PingEndpoints(self.matched.host1.int0, self.matched.host2.int0)]

    def generate_perf_endpoints(self, config):
        return [(self.matched.host1.int0, self.matched.host2.int0)]

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.int0, self.matched.host2.int0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
