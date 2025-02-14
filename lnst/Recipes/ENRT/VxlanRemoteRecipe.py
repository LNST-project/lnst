from collections.abc import Collection
from lnst.Common.IpAddress import ipaddress, interface_addresses
from lnst.Common.Parameters import IPv4NetworkParam
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.Recipes.ENRT.helpers import ip_endpoint_pairs
from lnst.Recipes.ENRT.BaremetalEnrtRecipe import BaremetalEnrtRecipe
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin
)
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin,
)
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Devices import VxlanDevice

class VxlanRemoteRecipe(
    CommonHWSubConfigMixin, OffloadSubConfigMixin, BaremetalEnrtRecipe
):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    net_ipv4 = IPv4NetworkParam(default="192.168.0.0/24")

    def test_wide_configuration(self, config):
        host1, host2 = self.matched.host1, self.matched.host2
        config = super().test_wide_configuration(config)

        for host in [host1, host2]:
            host.eth0.down()

        ipv4_addr = interface_addresses(self.params.net_ipv4)
        host1_ip = next(ipv4_addr)
        host2_ip = next(ipv4_addr)
        vxlan_net_addr = "192.168.100"
        vxlan_net_addr6 = "fc00:0:0:0"

        config.configure_and_track_ip(host1.eth0, host1_ip)
        host1.vxlan0 = VxlanDevice(vxlan_id='1', remote=host2_ip)
        config.configure_and_track_ip(host2.eth0, host2_ip)
        host2.vxlan0 = VxlanDevice(vxlan_id='1', remote=host1_ip)

        for i, host in enumerate([host1, host2], 1):
            host.vxlan0.realdev = host.eth0
            config.configure_and_track_ip(host.vxlan0, ipaddress(f"{vxlan_net_addr}.{i}/24"))
            config.configure_and_track_ip(host.vxlan0, ipaddress(f"{vxlan_net_addr6}::{i}/64"))

        for host in [host1, host2]:
            host.eth0.up_and_wait()
            host.vxlan0.up_and_wait()

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
                "Configured {}.{}.vxlan_id = {}".format(
                    dev.host.hostid, dev.name, dev.vxlan_id
                )
                for dev in [host1.vxlan0, host2.vxlan0]
            ]),
            "\n".join([
                "Configured {}.{}.remote = {}".format(
                    dev.host.hostid, dev.name, dev.remote
                )
                for dev in [host1.vxlan0, host2.vxlan0]
            ]),
            "\n".join([
                "Configured {}.{}.realdev = {}".format(
                    dev.host.hostid, dev.name,
                    '.'.join([dev.host.hostid, dev.realdev.name])
                )
                for dev in [host1.vxlan0, host2.vxlan0]
            ])
        ]
        return desc

    def generate_ping_endpoints(self, config):
        return [PingEndpoints(self.matched.host1.vxlan0, self.matched.host2.vxlan0)]

    def generate_perf_endpoints(self, config: EnrtConfiguration) -> list[Collection[EndpointPair[IPEndpoint]]]:
        return [ip_endpoint_pairs(config, (self.matched.host1.vxlan0, self.matched.host2.vxlan0))]

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.vxlan0, self.matched.host2.vxlan0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def offload_nics(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
