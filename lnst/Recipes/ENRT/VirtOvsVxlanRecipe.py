from collections.abc import Collection
from itertools import combinations
from lnst.Common.IpAddress import ipaddress, interface_addresses
from lnst.Common.Parameters import IPv4NetworkParam
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.Recipes.ENRT.helpers import ip_endpoint_pairs
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration
from lnst.Recipes.ENRT.VirtualEnrtRecipe import VirtualEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.Recipes.ENRT.PingMixins import VlanPingEvaluatorMixin
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Devices import OvsBridgeDevice

class VirtOvsVxlanRecipe(VlanPingEvaluatorMixin,
    CommonHWSubConfigMixin, VirtualEnrtRecipe):
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

    net_ipv4 = IPv4NetworkParam(default="192.168.2.0/24")


    def test_wide_configuration(self, config):
        host1, host2, guest1, guest2, guest3, guest4 = (self.matched.host1,
            self.matched.host2, self.matched.guest1, self.matched.guest2,
            self.matched.guest3, self.matched.guest4)

        for host in [host1, host2]:
            host.eth0.down()
            host.tap0.down()
            host.tap1.down()
        for guest in [guest1, guest2, guest3, guest4]:
            guest.eth0.down()

        net_addr = interface_addresses(self.params.net_ipv4)
        host_ips = [next(net_addr), next(net_addr)]
        vxlan_net_addr = "192.168.100"
        vxlan_net_addr6 = "fc00:0:0:0"

        flow_entries=[]
        flow_entries.append("table=0,in_port=5,actions=set_field:100->"
            "tun_id,output:10")
        flow_entries.append("table=0,in_port=6,actions=set_field:200->"
            "tun_id,output:10")
        flow_entries.append("table=0,in_port=10,tun_id=100,actions="
            "output:5")
        flow_entries.append("table=0,in_port=10,tun_id=200,actions="
            "output:6")
        flow_entries.append("table=0,priority=100,actions=drop")

        config = super().test_wide_configuration(config)

        for host, self_ip, other_ip in zip([host1, host2], host_ips, reversed(host_ips)):
            config.configure_and_track_ip(host.eth0, self_ip)
            host.br0 = OvsBridgeDevice()
            for dev, ofport_r in [(host.tap0, '5'), (host.tap1, '6')]:
                host.br0.port_add(
                        device=dev,
                        interface_options={'ofport_request': ofport_r})
            tunnel_opts = {"option:remote_ip" : other_ip,
                "option:key" : "flow", "ofport_request" : '10'}
            host.br0.tunnel_add("vxlan", tunnel_opts)
            host.br0.flows_add(flow_entries)
            for dev in [host.eth0, host.tap0, host.tap1, host.br0]:
                dev.up()

        for i, guest in enumerate([guest1, guest2, guest3, guest4], 1):
            config.configure_and_track_ip(guest.eth0, ipaddress(f"{vxlan_net_addr}.{i}/24"))
            config.configure_and_track_ip(guest.eth0, ipaddress(f"{vxlan_net_addr6}::{i}/64"))
            guest.eth0.up()

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

    def generate_ping_endpoints(self, config):
        guest1, guest2, guest3, guest4 = (self.matched.guest1,
            self.matched.guest2, self.matched.guest3, self.matched.guest4)
        devs = [guest1.eth0, guest2.eth0, guest3.eth0, guest4.eth0]
        dev_combinations = combinations(devs, 2)

        return [
            PingEndpoints(comb[0], comb[1],
                reachable=((comb[0].host, comb[1].host) in [
                    (guest1, guest3), (guest2, guest4)
                ])
            ) for comb in dev_combinations
        ]

    def generate_perf_endpoints(self, config: EnrtConfiguration) -> list[Collection[EndpointPair[IPEndpoint]]]:
        return [ip_endpoint_pairs(config, (self.matched.guest1.eth0, self.matched.guest3.eth0))]

    @property
    def pause_frames_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.guest1.eth0, self.matched.guest2.eth0,
            self.matched.guest3.eth0, self.matched.guest4.eth0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
