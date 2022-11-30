from typing import Union
from collections.abc import Generator

from lnst.Common.Parameters import Param, ListParam, StrParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaremetalEnrtRecipe import BaremetalEnrtRecipe
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin,
)

import ipaddress
from lnst.Devices.Device import Device

def get_interface_addresses(
        subnet: Union[ipaddress.IPv4Network, ipaddress.IPv6Network],
) -> Generator[ipaddress.IPv4Interface]:
    # This should be part of stdlib
    # See https://github.com/python/cpython/issues/86644
    host_addresses = subnet.hosts()
    for host in host_addresses:
        yield ipaddress.ip_interface((host,subnet.prefixlen))


class UniqueIPMixinSimple:

    test_net_ipv4 = ListParam(type=StrParam(), default=['192.168.0.0/24'])
    test_net_ipv6 = ListParam(type=StrParam(), default=["fc00:0::/48"])


    """
    Overwide this with
    """
    def assign_ip_addresses(
            self,
            interface_pairs: list[tuple[Device,Device]],
            ip_versions: tuple[str] = ("ipv4","ipv6"),
    ) -> Generator[Device]:
        """
        Generator that assigns addresses to device.

        As each interface is assigned its address it yielded back to the caller for further processing.
        Returns:

        """
        net_ipv4 = ipaddress.IPv4Network(self.params.test_net_ipv4[0])
        subnets_ipv4 = net_ipv4.subnets(prefixlen_diff=(len(interface_pairs)-1))

        net_ipv6 = ipaddress.IPv6Network(self.params.test_net_ipv6[0])
        subnets_ipv6 = net_ipv6.subnets(
            #prefixlen_diff=(len(interface_pairs)-1)*16,
            new_prefix=64
        )

        for iface1, iface2 in interface_pairs:

            if "ipv4" in ip_versions:
                subnet_ipv4 = next(subnets_ipv4)
                iface_addresses_ipv4 = get_interface_addresses(subnet_ipv4)
                iface1.ip_add(next(iface_addresses_ipv4).with_prefixlen)

            if "ipv6" in ip_versions:
                subnet_ipv6 = next(subnets_ipv6)
                iface_addresses_ipv6 = get_interface_addresses(subnet_ipv6)
                iface1.ip_add(next(iface_addresses_ipv6).with_prefixlen)

            #TODO Perhaps switch this to not call `ip_add` and just yield the interface and address.

            yield iface1

            if "ipv4" in ip_versions:
                iface2.ip_add(next(iface_addresses_ipv4).with_prefixlen)
            if "ipv6" in ip_versions:
                iface2.ip_add(next(iface_addresses_ipv6).with_prefixlen)

            yield iface2





class UniqueIPDemoRecipe(
    CommonHWSubConfigMixin, OffloadSubConfigMixin, BaremetalEnrtRecipe, UniqueIPMixinSimple
):
    """
    This recipe implements Enrt testing for a simple network scenario that looks
    as follows

    .. code-block:: none

                    +--------+
             +------+ switch +-----+
             |      +--------+     |
          +--+-+                 +-+--+
        +-|eth0|-+             +-|eth0|-+
        | +----+ |             | +----+ |
        | host1  |             | host2  |
        +--------+             +--------+

    All sub configurations are included via Mixin classes.

    The actual test machinery is implemented in the :any:`BaseEnrtRecipe` class.
    """
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="off", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="on", gso="off", tso="off", tx="on", rx="on"),
        dict(gro="on", gso="on", tso="off", tx="off", rx="on"),
        dict(gro="on", gso="on", tso="on", tx="on", rx="off")))

    def test_wide_configuration(self):
        """"""
        host1, host2 = self.matched.host1, self.matched.host2
        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = []

        interface_pairs = [(host1.eth0, host2.eth0)]

        for iface in self.assign_ip_addresses(interface_pairs):
            iface.up()
            configuration.test_wide_devices.append(iface)

        self.wait_tentative_ips(configuration.test_wide_devices)

        return configuration


    def old_test_wide_configuration(self):
        """
        Test wide configuration for this recipe involves just adding an IPv4 and
        IPv6 address to the matched eth0 nics on both hosts.

        host1.eth0 = 192.168.101.1/24 and fc00::1/64

        host2.eth0 = 192.168.101.2/24 and fc00::2/64
        """
        host1, host2 = self.matched.host1, self.matched.host2
        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = []

        for i, host in enumerate([host1, host2]):
            host.eth0.ip_add(ipaddress("192.168.101." + str(i+1) + "/24"))
            host.eth0.ip_add(ipaddress("fc00::" + str(i+1) + "/64"))
            host.eth0.up()
            configuration.test_wide_devices.append(host.eth0)

        self.wait_tentative_ips(configuration.test_wide_devices)

        return configuration

    def generate_test_wide_description(self, config):
        """
        Test wide description is extended with the configured addresses
        """
        desc = super().generate_test_wide_description(config)
        desc += [
            "Configured {}.{}.ips = {}".format(
                dev.host.hostid, dev.name, dev.ips
            )
            for dev in config.test_wide_devices
        ]
        return desc

    def test_wide_deconfiguration(self, config):
        ""  # overriding the parent docstring
        del config.test_wide_devices

        super().test_wide_deconfiguration(config)

    def generate_ping_endpoints(self, config):
        """
        The ping endpoints for this recipe are simply the two matched NICs:

        host1.eth0 and host2.eth0

        Returned as::

            [PingEndpoints(self.matched.host1.eth0, self.matched.host2.eth0)]
        """
        return [PingEndpoints(self.matched.host1.eth0, self.matched.host2.eth0)]

    def generate_perf_endpoints(self, config):
        """
        The perf endpoints for this recipe are simply the two matched NICs:

        host1.eth0 and host2.eth0

        Returned as::

            [(self.matched.host1.eth0, self.matched.host2.eth0)]
        """
        return [(self.matched.host1.eth0, self.matched.host2.eth0)]

    @property
    def pause_frames_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def offload_nics(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def coalescing_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
