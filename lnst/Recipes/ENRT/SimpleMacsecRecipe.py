from collections.abc import Iterator
import copy
from lnst.Common.IpAddress import interface_addresses
from lnst.Common.Parameters import Param, IPv4NetworkParam, IPv6NetworkParam
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Devices import MacsecDevice
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpointPair
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.Recipes.ENRT.helpers import ip_endpoint_pairs, ping_endpoint_pairs
from lnst.Recipes.ENRT.BaremetalEnrtRecipe import BaremetalEnrtRecipe
from lnst.Recipes.ENRT.EnrtConfiguration import EnrtConfiguration
from lnst.Recipes.ENRT.ConfigMixins.BaseSubConfigMixin import (
    BaseSubConfigMixin as ConfMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)


class SimpleMacsecRecipe(CommonHWSubConfigMixin, BaremetalEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    net_ipv4 = IPv4NetworkParam(default="192.168.100.0/24")
    net_ipv6 = IPv6NetworkParam(default="fc00::/64")

    macsec_encryption = Param(default=['on', 'off'])
    ids = ['00', '01']
    keys = ["7a16780284000775d4f0a3c0f0e092c0",
        "3212ef5c4cc5d0e4210b17208e88779e"]

    def test_wide_configuration(self):
        host1, host2 = self.matched.host1, self.matched.host2
        config = super().test_wide_configuration()

        config.endpoint1 = host1.eth0
        config.endpoint2 = host2.eth0
        config.host1 = host1
        config.host2 = host2

        return config

    def generate_sub_configurations(self, config):
        for subconf in ConfMixin.generate_sub_configurations(self, config):
            for encryption in self.params.macsec_encryption:
                new_config = copy.copy(subconf)
                new_config.encrypt = encryption
                new_config.ip_vers = self.params.ip_versions
                yield new_config

    def apply_sub_configuration(self, config: EnrtConfiguration):
        super().apply_sub_configuration(config)
        ipv4_addr = interface_addresses(self.params.net_ipv4)
        ipv6_addr = interface_addresses(self.params.net_ipv6)
        host1, host2 = config.host1, config.host2
        k_ids = list(zip(self.ids, self.keys))
        hosts_and_keys = [(host1, host2, k_ids), (host2, host1,
            k_ids[::-1])]
        for host_a, host_b, k_ids in hosts_and_keys:
            host_a.msec0 = MacsecDevice(realdev=host_a.eth0,
                encrypt=config.encrypt)
            rx_kwargs = dict(port=1, address=host_b.eth0.hwaddr)
            tx_sa_kwargs = dict(sa=0, pn=1, enable='on',
                id=k_ids[0][0], key=k_ids[0][1])
            rx_sa_kwargs = rx_kwargs.copy()
            rx_sa_kwargs.update(tx_sa_kwargs)
            rx_sa_kwargs['id'] = k_ids[1][0]
            rx_sa_kwargs['key'] = k_ids[1][1]
            host_a.msec0.rx('add', **rx_kwargs)
            host_a.msec0.tx_sa('add', **tx_sa_kwargs)
            host_a.msec0.rx_sa('add', **rx_sa_kwargs)
        for host in [host1, host2]:
            config.configure_and_track_ip(host.msec0, next(ipv4_addr))
            config.configure_and_track_ip(host.msec0, next(ipv6_addr))
            host.eth0.up()
            host.msec0.up()
            self.wait_tentative_ips([host.eth0, host.msec0])

    def generate_sub_configuration_description(self, config: EnrtConfiguration):
        desc = super().generate_sub_configuration_description(config)
        desc += [
            "\n".join([
                "Configured {}.{}.ips = {}".format(
                    dev.host.hostid, dev.name, dev.ips
                )
                for dev in config.configured_devices
            ])
        ]
        return desc

    def remove_sub_configuration(self, config):
        host1, host2 = config.host1, config.host2
        for host in (host1, host2):
            config.untrack_device(host.msec0)
            host.msec0.destroy()
            del host.msec0
        config.endpoint1.down()
        config.endpoint2.down()
        super().remove_sub_configuration(config)

    def generate_ping_endpoints(self, config: EnrtConfiguration) -> Iterator[list[PingEndpointPair]]:
        yield ping_endpoint_pairs(config, (self.matched.host1.msec0, self.matched.host2.msec0))

    def generate_perf_endpoints(self, config: EnrtConfiguration) -> Iterator[list[EndpointPair[IPEndpoint]]]:
        yield ip_endpoint_pairs(config, (self.matched.host1.msec0, self.matched.host2.msec0))

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
