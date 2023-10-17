from collections.abc import Iterator
from lnst.Common.Parameters import (
    Param,
    IntParam,
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
from lnst.Recipes.ENRT.ConfigMixins.PerfReversibleFlowMixin import (
    PerfReversibleFlowMixin)
from lnst.Devices import TeamDevice
from lnst.Devices import BondDevice

class TeamVsBondRecipe(PerfReversibleFlowMixin, CommonHWSubConfigMixin,
    OffloadSubConfigMixin, BaremetalEnrtRecipe):
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

    runner_name = StrParam(mandatory = True)
    bonding_mode = StrParam(mandatory = True)
    miimon_value = IntParam(mandatory = True)

    def test_wide_configuration(self):
        host1, host2 = self.matched.host1, self.matched.host2

        host1.team0 = TeamDevice(config={'runner': {'name': self.params.runner_name}})

        host2.bond0 = BondDevice(mode=self.params.bonding_mode,
            miimon=self.params.miimon_value)

        config = super().test_wide_configuration()
        ipv4_addr = interface_addresses(self.params.net_ipv4)
        ipv6_addr = interface_addresses(self.params.net_ipv6)

        for (host, dev) in [(host1, host1.team0), (host2, host2.bond0)]:
            host.eth0.down()
            host.eth1.down()
            dev.slave_add(host.eth0)
            dev.slave_add(host.eth1)
            config.configure_and_track_ip(dev, next(ipv4_addr))
            config.configure_and_track_ip(dev, next(ipv6_addr))

        for host, dev in [(host1, host1.team0), (host2, host2.bond0)]:
            host.eth0.up()
            host.eth1.up()
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
            "Configured {}.{}.runner_name = {}".format(
                host1.hostid, host1.team0.name,
                host1.team0.config
            ),
            "Configured {}.{}.mode = {}".format(
                host2.hostid, host2.bond0.name,
                host2.bond0.mode
            ),
            "Configured {}.{}.miimon = {}".format(
                host2.hostid, host2.bond0.name,
                host2.bond0.miimon
            )
        ]
        return desc

    def generate_ping_endpoints(self, config: EnrtConfiguration) -> Iterator[list[PingEndpointPair]]:
        yield ping_endpoint_pairs(config, (self.matched.host1.team0, self.matched.host2.bond0))
        yield ping_endpoint_pairs(config, (self.matched.host2.bond0, self.matched.host1.team0))

    def generate_perf_endpoints(self, config: EnrtConfiguration) -> Iterator[list[EndpointPair[IPEndpoint]]]:
        yield ip_endpoint_pairs(config, (self.matched.host1.team0, self.matched.host2.bond0))

    @property
    def offload_nics(self):
        return [self.matched.host1.team0, self.matched.host2.bond0]

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.team0, self.matched.host2.bond0]

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
