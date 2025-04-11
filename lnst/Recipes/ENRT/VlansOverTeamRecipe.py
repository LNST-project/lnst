from collections.abc import Collection
from lnst.Common.Parameters import (
    Param,
    IntParam,
    StrParam,
    IPv4NetworkParam,
    IPv6NetworkParam,
)
from lnst.Common.IpAddress import interface_addresses
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.Recipes.ENRT.helpers import ip_endpoint_pairs
from lnst.Recipes.ENRT.BaremetalEnrtRecipe import BaremetalEnrtRecipe
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.PerfReversibleFlowMixin import (
    PerfReversibleFlowMixin)
from lnst.Recipes.ENRT.PingMixins import VlanPingEvaluatorMixin
from lnst.Recipes.ENRT.RecipeReqs import BondOrTeamReq
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Devices import VlanDevice
from lnst.Devices.VlanDevice import VlanDevice as Vlan
from lnst.Devices import TeamDevice


class VlansOverTeamRecipe(PerfReversibleFlowMixin, VlanPingEvaluatorMixin,
    CommonHWSubConfigMixin, OffloadSubConfigMixin,
    BondOrTeamReq, BaremetalEnrtRecipe):
    vlan0_id = IntParam(default=10)
    vlan1_id = IntParam(default=20)
    vlan2_id = IntParam(default=30)

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on"),
        dict(gro="off", gso="on", tso="on", tx="on"),
        dict(gro="on", gso="off", tso="off", tx="on"),
        dict(gro="on", gso="on", tso="off", tx="off")))

    vlan0_ipv4 = IPv4NetworkParam(default="192.168.10.0/24")
    vlan0_ipv6 = IPv6NetworkParam(default="fc00:0:0:1::/64")

    vlan1_ipv4 = IPv4NetworkParam(default="192.168.20.0/24")
    vlan1_ipv6 = IPv6NetworkParam(default="fc00:0:0:2::/64")

    vlan2_ipv4 = IPv4NetworkParam(default="192.168.30.0/24")
    vlan2_ipv6 = IPv6NetworkParam(default="fc00:0:0:3::/64")

    runner_name = StrParam(mandatory = True)

    def test_wide_configuration(self, config):
        host1, host2 = self.matched.host1, self.matched.host2
        config = super().test_wide_configuration(config)

        host1.team0 = TeamDevice(config={'runner': {'name': self.params.runner_name}})
        for dev in [host1.eth0, host1.eth1]:
            dev.down()
            host1.team0.slave_add(dev)

        host1.vlan0 = VlanDevice(realdev=host1.team0, vlan_id=self.params.vlan0_id)
        host1.vlan1 = VlanDevice(realdev=host1.team0, vlan_id=self.params.vlan1_id)
        host1.vlan2 = VlanDevice(realdev=host1.team0, vlan_id=self.params.vlan2_id)
        host2.vlan0 = VlanDevice(realdev=host2.eth0, vlan_id=self.params.vlan0_id)
        host2.vlan1 = VlanDevice(realdev=host2.eth0, vlan_id=self.params.vlan1_id)
        host2.vlan2 = VlanDevice(realdev=host2.eth0, vlan_id=self.params.vlan2_id)

        config.track_device(host1.team0)

        vlan0_ipv4_addr = interface_addresses(self.params.vlan0_ipv4)
        vlan0_ipv6_addr = interface_addresses(self.params.vlan0_ipv6)
        vlan1_ipv4_addr = interface_addresses(self.params.vlan1_ipv4)
        vlan1_ipv6_addr = interface_addresses(self.params.vlan1_ipv6)
        vlan2_ipv4_addr = interface_addresses(self.params.vlan2_ipv4)
        vlan2_ipv6_addr = interface_addresses(self.params.vlan2_ipv6)

        for host in [host1, host2]:
            config.configure_and_track_ip(host.vlan0, next(vlan0_ipv4_addr))
            config.configure_and_track_ip(host.vlan1, next(vlan1_ipv4_addr))
            config.configure_and_track_ip(host.vlan2, next(vlan2_ipv4_addr))
            config.configure_and_track_ip(host.vlan0, next(vlan0_ipv6_addr))
            config.configure_and_track_ip(host.vlan1, next(vlan1_ipv6_addr))
            config.configure_and_track_ip(host.vlan2, next(vlan2_ipv6_addr))

        for dev in [host1.eth0, host1.eth1, host1.team0, host1.vlan0,
            host1.vlan1, host1.vlan2, host2.eth0, host2.vlan0, host2.vlan1,
            host2.vlan2]:
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
                for dev in config.configured_devices if isinstance(dev,
                    Vlan)
            ]),
            "\n".join([
                "Configured {}.{}.vlan_id = {}".format(
                    dev.host.hostid, dev.name, dev.vlan_id
                )
                for dev in config.configured_devices if isinstance(dev,
                    Vlan)
            ]),
            "\n".join([
                "Configured {}.{}.realdev = {}".format(
                    dev.host.hostid, dev.name,
                    '.'.join([dev.host.hostid, dev.realdev.name])
                )
                for dev in config.configured_devices if isinstance(dev,
                    Vlan)
            ]),
            "Configured {}.{}.slaves = {}".format(
                host1.hostid, host1.team0.name,
                ['.'.join([host1.hostid, slave.name])
                for slave in host1.team0.slaves]
            ),
            "Configured {}.{}.runner_name = {}".format(
                host1.hostid, host1.team0.name,
                host1.team0.config
            )
        ]
        return desc

    def generate_ping_endpoints(self, config):
        host1, host2 = self.matched.host1, self.matched.host2

        return [PingEndpoints(host1.vlan0, host2.vlan0),
                PingEndpoints(host1.vlan1, host2.vlan1),
                PingEndpoints(host1.vlan2, host2.vlan2)]

    def generate_perf_endpoints(self, config: EnrtConfiguration) -> list[Collection[EndpointPair[IPEndpoint]]]:
        return [ip_endpoint_pairs(config, (self.matched.host1.vlan0, self.matched.host2.vlan0))]

    @property
    def offload_nics(self):
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0]

    @property
    def mtu_hw_config_dev_list(self):
        host1, host2 = self.matched.host1, self.matched.host2
        result = []
        for host in [host1, host2]:
            for dev in [host.vlan0, host.vlan1, host.vlan2]:
                result.append(dev)
        result.extend([host1.team0, host2.eth0])
        return result

    @property
    def dev_interrupt_hw_config_dev_list(self):
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0]
