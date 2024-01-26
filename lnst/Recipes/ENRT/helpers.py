from collections.abc import Collection, Iterable
from typing import TypeVar
import itertools

from lnst.Common.IpAddress import BaseIpAddress, Ip4Address, Ip6Address
from lnst.Devices import RemoteDevice
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpointPair
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.Recipes.ENRT.EnrtConfiguration import EnrtConfiguration


def ip_endpoint_pairs(
    config: EnrtConfiguration, *device_pairs: tuple[RemoteDevice, RemoteDevice]
) -> list[EndpointPair[IPEndpoint]]:
    """Helper function for use in generate_perf_endpoints method.

    Generates a sequential endpoint pair list for each input device pair.
    """
    endpoint_pairs = []
    for dev1, dev2 in device_pairs:
        for ip_type in [Ip4Address, Ip6Address]:
            dev1_ips = [ip for ip in config.ips_for_device(dev1) if isinstance(ip, ip_type)]
            dev2_ips = [ip for ip in config.ips_for_device(dev2) if isinstance(ip, ip_type)]

            for ip1, ip2 in itertools.product(dev1_ips, dev2_ips):
                endpoint_pairs.append(
                    EndpointPair(
                        IPEndpoint(dev1, ip1),
                        IPEndpoint(dev2, ip2),
                    )
                )

    return endpoint_pairs


def ping_endpoint_pairs(
    config: EnrtConfiguration,
    *device_pairs: tuple[RemoteDevice, RemoteDevice],
    should_be_reachable: bool = True,
) -> list[PingEndpointPair]:
    """Helper function for use in generate_ping_endpoints method.

    Generates a sequential endpoint pair list for each input device pair.
    """
    endpoint_pairs = []
    for dev1, dev2 in device_pairs:
        for ip_type in [Ip4Address, Ip6Address]:
            dev1_ips = [ip for ip in config.ips_for_device(dev1) if isinstance(ip, ip_type)]
            dev2_ips = [ip for ip in config.ips_for_device(dev2) if isinstance(ip, ip_type)]

            for ip1, ip2 in itertools.product(dev1_ips, dev2_ips):
                endpoint_pairs.append(
                    PingEndpointPair(
                        IPEndpoint(dev1, ip1),
                        IPEndpoint(dev2, ip2),
                        should_be_reachable=should_be_reachable,
                    )
                )

    return endpoint_pairs


TIPEndpointPair = TypeVar("TIPEndpointPair", bound=EndpointPair[IPEndpoint])

def filter_ip_endpoint_pairs(ip_versions: Collection[str], endpoint_pairs: Iterable[TIPEndpointPair]) -> list[TIPEndpointPair]:
    def ip_version_string(ip_address: BaseIpAddress) -> str:
        return "ipv4" if isinstance(ip_address, Ip4Address) else "ipv6"

    return [
        endpoint_pair
        for endpoint_pair in endpoint_pairs
        if ip_version_string(endpoint_pair.first.address) in ip_versions
    ]
