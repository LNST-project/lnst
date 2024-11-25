from collections.abc import Collection
from lnst.Common.Parameters import (
    Param,
    IPv4NetworkParam,
    IPv6NetworkParam,
)
from lnst.Common.IpAddress import interface_addresses
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.Recipes.ENRT.helpers import ip_endpoint_pairs
from lnst.Recipes.ENRT.BaremetalEnrtRecipe import BaremetalEnrtRecipe
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.Recipes.ENRT.BondingMixin import BondingMixin
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints


class DoubleBondRecipe(BondingMixin, CommonHWSubConfigMixin, OffloadSubConfigMixin,
    BaremetalEnrtRecipe):
    """
    This recipe implements Enrt testing for a network scenario that looks
    as follows

    .. code-block:: none

                                    .--------.
                   .----------------+        +------------------.
                   |        .-------+ switch +---------.        |
                   |        |       '--------'         |        |
             .-------------------.               .-------------------.
             |     | bond0  |    |               |     | bond0  |    |
             | .---'--. .---'--. |               | .---'--. .---'--. |
        .----|-| eth0 |-| eth1 |-|----.     .----|-| eth0 |-| eth1 |-|----.
        |    | '------' '------' |    |     |    | '------' '------' |    |
        |    '-------------------'    |     |    '-------------------'    |
        |                             |     |                             |
        |            host1            |     |            host2            |
        '-----------------------------'     '-----------------------------'

    Refer to :any:`BondingMixin` for parameters to configure the bonding
    device.

    All sub configurations are included via Mixin classes.

    The actual test machinery is implemented in the :any:`BaseEnrtRecipe` class.
    """
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))
    host1.eth1 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))
    host2.eth1 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on"),
        dict(gro="off", gso="on", tso="on", tx="on"),
        dict(gro="on", gso="off", tso="off", tx="on"),
        dict(gro="on", gso="on", tso="off", tx="off")))

    net_ipv4 = IPv4NetworkParam(default="192.168.101.0/24")
    net_ipv6 = IPv6NetworkParam(default="fc00::/64")

    def test_wide_configuration(self, config):
        host1, host2 = self.matched.host1, self.matched.host2
        config = super().test_wide_configuration(config)

        ipv4_addr = interface_addresses(self.params.net_ipv4)
        ipv6_addr = interface_addresses(self.params.net_ipv6)

        self.create_bond_devices(
            config,
            {
                "host1": {
                    "bond0": [host1.eth0, host1.eth1]
                },
                "host2": {
                    "bond0": [host2.eth0, host2.eth1]
                }
            }
        )

        for host in [host1, host2]:
            config.configure_and_track_ip(host.bond0, next(ipv4_addr))
            config.configure_and_track_ip(host.bond0, next(ipv6_addr))
            for dev in [host.eth0, host.eth1, host.bond0]:
                dev.up_and_wait()

        self.wait_tentative_ips(config.configured_devices)

        return config

    def generate_test_wide_description(self, config: EnrtConfiguration):
        desc = super().generate_test_wide_description(config)
        desc += [
            "\n".join([
                "Configured {}.{}.ips = {}".format(
                    dev.host.hostid, dev.name, dev.ips
                )
                for dev in config.configured_devices
            ])
        ]

        return desc

    def generate_ping_endpoints(self, config):
        return [PingEndpoints(self.matched.host1.bond0, self.matched.host2.bond0)]

    def generate_perf_endpoints(self, config: EnrtConfiguration) -> list[Collection[EndpointPair[IPEndpoint]]]:
        return [ip_endpoint_pairs(config, (self.matched.host1.bond0, self.matched.host2.bond0))]

    @property
    def offload_nics(self):
        return [self.matched.host1.bond0, self.matched.host2.bond0]

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.bond0, self.matched.host2.bond0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0, host2.eth1]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0, host2.eth1]

    @property
    def vf_trust_dev_list(self):
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0, host2.eth1]
