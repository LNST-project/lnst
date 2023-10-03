from collections.abc import Collection, Iterator
from lnst.Common.Parameters import IPv4NetworkParam
from lnst.Common.IpAddress import ipaddress, interface_addresses
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpointPair
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.Recipes.ENRT.helpers import ip_endpoint_pairs, ping_endpoint_pairs
from lnst.Recipes.ENRT.BaremetalEnrtRecipe import BaremetalEnrtRecipe
from lnst.Recipes.ENRT.EnrtConfiguration import EnrtConfiguration
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.Devices import OvsBridgeDevice

class NoVirtOvsVxlanRecipe(CommonHWSubConfigMixin, BaremetalEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    net_ipv4 = IPv4NetworkParam(default="192.168.2.0/24")

    def test_wide_configuration(self):
        host1, host2 = self.matched.host1, self.matched.host2
        config = super().test_wide_configuration()

        ipv4_addr = interface_addresses(self.params.net_ipv4)
        host_addr = [next(ipv4_addr), next(ipv4_addr)]
        vxlan_net_addr = "192.168.100"
        vxlan_net_addr6 = "fc00:0:0:0"

        flow_entries=[]
        flow_entries.append("table=0,in_port=5,actions=set_field:100->"
            "tun_id,output:10")
        flow_entries.append("table=0,in_port=10,tun_id=100,actions="
            "output:5")
        flow_entries.append("table=0,priority=100,actions=drop")

        for i, (host, self_ip, other_ip) in enumerate(
            zip([host1, host2], host_addr, reversed(host_addr)), 1
        ):
            host.eth0.down()
            config.configure_and_track_ip(host.eth0, self_ip)
            host.br0 = OvsBridgeDevice()
            host.int0 = host.br0.port_add(
                    interface_options={
                        'type': 'internal',
                        'ofport_request': 5,
                        'name': 'int0'})
            config.configure_and_track_ip(host.int0, ipaddress(f"{vxlan_net_addr}.{i}/24"))
            config.configure_and_track_ip(host.int0, ipaddress(f"{vxlan_net_addr6}::{i}/64"))
            tunnel_opts = {"option:remote_ip" : other_ip,
                           "option:key" : "flow", "ofport_request" : "10"}
            host.br0.tunnel_add("vxlan", tunnel_opts)
            host.br0.flows_add(flow_entries)
            host.eth0.up()
            host.int0.up()
            host.br0.up()

        self.wait_tentative_ips(config.configured_devices)

        return config

    def generate_test_wide_description(self, config: EnrtConfiguration):
        host1, host2 = self.matched.host1, self.matched.host2
        desc = super().generate_test_wide_description(config)
        desc += [
            "\n".join([
                "Configured {}.{}.ips = {}".format(
                    dev.host.hostid, dev.name, dev.ips
                )
                for dev in config.configured_devices
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

    def generate_ping_endpoints(self, config: EnrtConfiguration) -> Iterator[Collection[PingEndpointPair]]:
        yield ping_endpoint_pairs(config, (self.matched.host1.int0, self.matched.host2.int0))

    def generate_perf_endpoints(self, config: EnrtConfiguration) -> Iterator[Collection[EndpointPair[IPEndpoint]]]:
        yield ip_endpoint_pairs(config, (self.matched.host1.int0, self.matched.host2.int0))

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.int0, self.matched.host2.int0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
