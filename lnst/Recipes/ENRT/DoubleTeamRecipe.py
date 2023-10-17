from collections.abc import Iterator
from lnst.Common.Parameters import (
    Param,
    StrParam,
    IPv4NetworkParam,
    IPv6NetworkParam,
)
from lnst.Common.IpAddress import interface_addresses
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpointPair
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.Recipes.ENRT.helpers import ip_endpoint_pairs, ping_endpoint_pairs
from lnst.Recipes.ENRT.BaremetalEnrtRecipe import BaremetalEnrtRecipe
from lnst.Recipes.ENRT.EnrtConfiguration import EnrtConfiguration
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.Devices import TeamDevice

class DoubleTeamRecipe(CommonHWSubConfigMixin, OffloadSubConfigMixin,
    BaremetalEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="tnet", driver=RecipeParam("driver"))
    host1.eth1 = DeviceReq(label="tnet", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="tnet", driver=RecipeParam("driver"))
    host2.eth1 = DeviceReq(label="tnet", driver=RecipeParam("driver"))

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on"),
        dict(gro="off", gso="on", tso="on", tx="on"),
        dict(gro="on", gso="off", tso="off", tx="on"),
        dict(gro="on", gso="on", tso="off", tx="off")))

    net_ipv4 = IPv4NetworkParam(default="192.168.10.0/24")
    net_ipv6 = IPv6NetworkParam(default='fc00:0:0:1::/64')

    runner_name = StrParam(mandatory=True)

    def test_wide_configuration(self):
        host1, host2 = self.matched.host1, self.matched.host2
        config = super().test_wide_configuration()

        ipv4_addr = interface_addresses(self.params.net_ipv4)
        ipv6_addr = interface_addresses(self.params.net_ipv6)
        for host in [host1, host2]:
            host.team0 = TeamDevice(
                    config={'runner': {'name': self.params.runner_name}}
                    )
            for dev in [host.eth0, host.eth1]:
                dev.down()
                host.team0.slave_add(dev)
            config.configure_and_track_ip(host.team0, next(ipv4_addr))
            config.configure_and_track_ip(host.team0, next(ipv6_addr))
            for dev in [host.eth0, host.eth1, host.team0]:
                dev.up()

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
                "Configured {}.{}.slaves = {}".format(
                    dev.host.hostid, dev.name,
                    ['.'.join([dev.host.hostid, slave.name])
                    for slave in dev.slaves]
                )
                for dev in config.configured_devices
            ]),
            "\n".join([
                "Configured {}.{}.runner_name = {}".format(
                    dev.host.hostid, dev.name, dev.config
                )
                for dev in config.configured_devices
            ])
        ]
        return desc

    def generate_ping_endpoints(self, config: EnrtConfiguration) -> Iterator[PingEndpointPair]:
        yield from ping_endpoint_pairs(config, (self.matched.host1.team0, self.matched.host2.team0))
        yield from ping_endpoint_pairs(config, (self.matched.host2.team0, self.matched.host1.team0))

    def generate_perf_endpoints(self, config: EnrtConfiguration) -> Iterator[list[EndpointPair[IPEndpoint]]]:
        yield ip_endpoint_pairs(config, (self.matched.host1.team0, self.matched.host2.team0))

    @property
    def offload_nics(self):
        return [self.matched.host1.team0, self.matched.host2.team0]

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.team0, self.matched.host2.team0]

    @property
    def coalescing_hw_config_dev_list(self):
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0, host2.eth1]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0, host2.eth1]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0, host2.eth1]
