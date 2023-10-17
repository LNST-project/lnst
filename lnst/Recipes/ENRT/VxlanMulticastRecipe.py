from collections.abc import Iterator
from itertools import combinations
from socket import AF_INET
from lnst.Common.IpAddress import ipaddress, interface_addresses
from lnst.Common.Parameters import IpParam, IPv4NetworkParam
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpointPair
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.Recipes.ENRT.helpers import ip_endpoint_pairs, ping_endpoint_pairs
from lnst.Recipes.ENRT.EnrtConfiguration import EnrtConfiguration
from lnst.Recipes.ENRT.VirtualEnrtRecipe import VirtualEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.Devices import BridgeDevice, VxlanDevice

class VxlanMulticastRecipe(CommonHWSubConfigMixin, VirtualEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))
    host1.tap0 = DeviceReq(label="to_guest1")

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    guest1 = HostReq()
    guest1.eth0 = DeviceReq(label="to_guest1")

    net_ipv4 = IPv4NetworkParam(default="192.168.0.0/24")
    vxlan_group_ip = IpParam(default="239.1.1.1", multicast=True, family=AF_INET)

    def test_wide_configuration(self):
        host1, host2, guest1 = (self.matched.host1, self.matched.host2,
            self.matched.guest1)

        for dev in [host1.eth0, host2.eth0, guest1.eth0, host1.tap0]:
            dev.down()

        ipv4_addr = interface_addresses(self.params.net_ipv4)
        vxlan_net_addr = "192.168.100"
        vxlan_net_addr6 = "fc00:0:0:0"

        host1.br0 = BridgeDevice()
        host1.br0.slave_add(host1.eth0)
        host1.br0.slave_add(host1.tap0)

        host1.vxlan0 = VxlanDevice(vxlan_id=1, realdev=host1.br0, group=self.params.vxlan_group_ip)
        for machine in [guest1, host2]:
            machine.vxlan0 = VxlanDevice(vxlan_id=1, realdev=machine.eth0, group=self.params.vxlan_group_ip)

        config = super().test_wide_configuration()

        for i, (machine, dev) in enumerate([(host1, host1.br0),
            (guest1, guest1.eth0), (host2, host2.eth0)], 1):
            config.configure_and_track_ip(dev, next(ipv4_addr))
            dev.ip_add(next(ipv4_addr))
            machine.vxlan0.realdev = dev
            config.configure_and_track_ip(machine.vxlan0, ipaddress(f"{vxlan_net_addr}.{i}/24"))
            config.configure_and_track_ip(machine.vxlan0, ipaddress(f"{vxlan_net_addr6}::{i}/64"))

        for dev in [host1.eth0, host2.eth0, guest1.eth0, host1.tap0,
                    host1.br0, host1.vxlan0, host2.vxlan0, guest1.vxlan0]:
            dev.up()

        self.wait_tentative_ips(config.configured_devices)

        return config

    def generate_test_wide_description(self, config: EnrtConfiguration):
        host1, host2, guest1 = (self.matched.host1, self.matched.host2,
            self.matched.guest1)
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
                for dev in [host1.vxlan0, host2.vxlan0, guest1.vxlan0]
            ]),
            "\n".join([
                "Configured {}.{}.group = {}".format(
                    dev.host.hostid, dev.name, dev.group
                )
                for dev in [host1.vxlan0, host2.vxlan0, guest1.vxlan0]
            ]),
            "\n".join([
                "Configured {}.{}.realdev = {}".format(
                    dev.host.hostid, dev.name,
                    '.'.join([dev.host.hostid, dev.realdev.name])
                )
                for dev in [host1.vxlan0, host2.vxlan0, guest1.vxlan0]
            ])
        ]
        return desc

    def generate_ping_endpoints(self, config: EnrtConfiguration) -> Iterator[PingEndpointPair]:
        host1, host2, guest1 = (self.matched.host1, self.matched.host2, self.matched.guest1)
        devs = [host1.vxlan0, host2.vxlan0, guest1.vxlan0]
        for dev1, dev2 in combinations(devs, 2):
            yield from ping_endpoint_pairs(config, (dev1, dev2))

    def generate_perf_endpoints(self, config: EnrtConfiguration) -> Iterator[list[EndpointPair[IPEndpoint]]]:
        yield ip_endpoint_pairs(config, (self.matched.host1.vxlan0, self.matched.host2.vxlan0))

    @property
    def mtu_hw_config_dev_list(self):
        host1, host2, guest1 = (self.matched.host1, self.matched.host2,
            self.matched.guest1)
        return [host1.vxlan0, host2.vxlan0, guest1.vxlan0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
