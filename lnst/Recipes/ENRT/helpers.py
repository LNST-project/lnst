from collections.abc import Collection, Iterator
import itertools

from lnst.Common.IpAddress import Ip4Address, Ip6Address
from lnst.Devices import RemoteDevice
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration


def ip_endpoint_pairs(
    config: EnrtConfiguration, *device_pairs: tuple[RemoteDevice, RemoteDevice]
) -> Collection[EndpointPair[IPEndpoint]]:
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
