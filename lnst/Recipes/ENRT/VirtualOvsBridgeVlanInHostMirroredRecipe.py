from collections.abc import Collection
import logging
from lnst.Common.Parameters import Param, IntParam, IPv4NetworkParam, IPv6NetworkParam
from lnst.Common.IpAddress import interface_addresses
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.Recipes.ENRT.helpers import ip_endpoint_pairs
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration
from lnst.Recipes.ENRT.VirtualEnrtRecipe import VirtualEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Devices import OvsBridgeDevice
from lnst.Recipes.ENRT.RecipeReqs import VirtualBridgeMirroredReq


class VirtualOvsBridgeVlanInHostMirroredRecipe(CommonHWSubConfigMixin,
    OffloadSubConfigMixin, VirtualBridgeMirroredReq, VirtualEnrtRecipe):
    vlan_id = IntParam(default=10)

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="off", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="on", gso="off", tso="off", tx="on", rx="on"),
        dict(gro="on", gso="on", tso="off", tx="off", rx="on"),
        dict(gro="on", gso="on", tso="on", tx="on", rx="off")))

    net_ipv4 = IPv4NetworkParam(default="192.168.10.0/24")
    net_ipv6 = IPv6NetworkParam(default="fc00:0:0:1::/64")

    def test_wide_configuration(self, config):
        host1, host2, guest1, guest2 = (self.matched.host1,
            self.matched.host2, self.matched.guest1, self.matched.guest2)

        for host in [host1, host2]:
            host.br0 = OvsBridgeDevice()
            host.eth0.down()
            host.tap0.down()
            host.br0.port_add(host.eth0)
            host.br0.port_add(host.tap0, port_options={'tag': self.params.vlan_id})

        guest1.eth0.down()
        guest2.eth0.down()

        config = super().test_wide_configuration(config)

        ipv4_addr = interface_addresses(self.params.net_ipv4, default_start="192.168.10.3/24")
        ipv6_addr = interface_addresses(self.params.net_ipv6, default_start="fc00:0:0:1::3/64")
        for guest in [guest1, guest2]:
            config.configure_and_track_ip(guest.eth0, next(ipv4_addr))
            config.configure_and_track_ip(guest.eth0, next(ipv6_addr))

        for host in [host1, host2]:
            for dev in [host.eth0, host.tap0, host.br0]:
                dev.up()
        guest1.eth0.up()
        guest2.eth0.up()

        if "perf_tool_cpu" in self.params:
            logging.info("'perf_tool_cpu' param (%d) to be set to None" %
                self.params.perf_tool_cpu)
            self.params.perf_tool_cpu = None

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
            ])
        ]
        return desc

    def generate_ping_endpoints(self, config):
        return [PingEndpoints(self.matched.guest1.eth0, self.matched.guest2.eth0)]

    def generate_perf_endpoints(self, config: EnrtConfiguration) -> list[Collection[EndpointPair[IPEndpoint]]]:
        return [ip_endpoint_pairs(config, (self.matched.guest1.eth0, self.matched.guest2.eth0))]

    @property
    def offload_nics(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0,
            self.matched.guest1.eth0, self.matched.guest2.eth0]

    @property
    def mtu_hw_config_dev_list(self):
        host1, host2, guest1, guest2 = (self.matched.host1,
            self.matched.host2, self.matched.guest1, self.matched.guest2)
        result = []
        for host in [host1, host2]:
            for dev in [host.eth0, host.tap0, host.br0]:
                result.append(dev)
        for guest in [guest1, guest2]:
            result.append(guest.eth0)
        return result

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
