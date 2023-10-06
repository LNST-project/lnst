from collections.abc import Collection, Iterator
import logging
from lnst.Common.Parameters import (
    Param,
    IntParam,
    IPv4NetworkParam,
    IPv6NetworkParam,
)
from lnst.Common.IpAddress import interface_addresses
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.Recipes.ENRT.helpers import ip_endpoint_pairs
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration
from lnst.Recipes.ENRT.VirtualEnrtRecipe import VirtualEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Devices import VlanDevice
from lnst.Devices import BridgeDevice

class VirtualBridgeVlanInHostMirroredRecipe(CommonHWSubConfigMixin,
    OffloadSubConfigMixin, VirtualEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))
    host1.tap0 = DeviceReq(label="to_guest1")

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))
    host2.tap0 = DeviceReq(label="to_guest2")

    guest1 = HostReq()
    guest1.eth0 = DeviceReq(label="to_guest1")

    guest2 = HostReq()
    guest2.eth0 = DeviceReq(label="to_guest2")

    vlan_id = IntParam(default=10)

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="off", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="on", gso="off", tso="off", tx="on", rx="on"),
        dict(gro="on", gso="on", tso="off", tx="off", rx="on"),
        dict(gro="on", gso="on", tso="on", tx="on", rx="off")))

    net_ipv4 = IPv4NetworkParam(default="192.168.10.0/24")
    net_ipv6 = IPv6NetworkParam(default="fc00:0:0:1::/64")

    def test_wide_configuration(self):
        host1, host2, guest1, guest2 = (self.matched.host1,
            self.matched.host2, self.matched.guest1, self.matched.guest2)

        for host in [host1, host2]:
            host.eth0.down()
            host.tap0.down()
            host.br0 = BridgeDevice()
            host.br0.slave_add(host.tap0)

        guest1.eth0.down()
        guest2.eth0.down()

        host1.vlan0 = VlanDevice(realdev=host1.eth0, vlan_id=self.params.vlan_id,
            master=host1.br0)
        host2.vlan0 = VlanDevice(realdev=host2.eth0, vlan_id=self.params.vlan_id,
            master=host2.br0)

        config = super().test_wide_configuration()

        ipv4_addr = interface_addresses(self.params.net_ipv4)
        ipv6_addr = interface_addresses(self.params.net_ipv6, default_start="fc00:0:0:1::3/64")

        config.configure_and_track_ip(host1.br0, next(ipv4_addr))
        config.configure_and_track_ip(host2.br0, next(ipv4_addr))
        for guest in [guest1, guest2]:
            config.configure_and_track_ip(guest.eth0, next(ipv4_addr))
            config.configure_and_track_ip(guest.eth0, next(ipv6_addr))

        for host in [host1, host2]:
            for dev in [host.eth0, host.tap0, host.vlan0, host.br0]:
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
                "Configured {}.{}.vlan_id = {}".format(
                    dev.host.hostid, dev.name, dev.vlan_id
                )
                for dev in [host1.vlan0, host2.vlan0]
            ]),
            "\n".join([
                "Configured {}.{}.realdev = {}".format(
                    dev.host.hostid, dev.name,
                    '.'.join([dev.host.hostid, dev.realdev.name])
                )
                for dev in [host1.vlan0, host2.vlan0]
            ]),
            "\n".join([
                "Configured {}.{}.slaves = {}".format(
                    dev.host.hostid, dev.name,
                    ['.'.join([dev.host.hostid, slave.name])
                    for slave in dev.slaves]
                )
                for dev in [host1.br0, host2.br0]
            ])
        ]
        return desc

    def generate_ping_endpoints(self, config):
        return [PingEndpoints(self.matched.guest1.eth0, self.matched.guest2.eth0)]

    def generate_perf_endpoints(self, config: EnrtConfiguration) -> Iterator[Collection[EndpointPair[IPEndpoint]]]:
        yield ip_endpoint_pairs(config, (self.matched.guest1.eth0, self.matched.guest2.eth0))

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
            for dev in [host.eth0, host.tap0, host.br0, host.vlan0]:
                result.append(dev)
        result.extend([guest1.eth0, guest2.eth0])
        return result

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
