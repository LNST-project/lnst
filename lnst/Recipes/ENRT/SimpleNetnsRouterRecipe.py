from lnst.Recipes.ENRT.SimpleNetworkRecipe import SimpleNetworkRecipe
from lnst.Common.Parameters import IPv4NetworkParam, IPv6NetworkParam
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Recipes.ENRT.helpers import ip_endpoint_pairs
from lnst.Controller.NetNamespace import NetNamespace
from lnst.Common.IpAddress import interface_addresses
from lnst.Devices.VethPair import VethPair
from collections.abc import Collection

class SimpleNetnsRouterRecipe(SimpleNetworkRecipe):
    """
    This recipe implements Enrt testing for a simple network scenario that
    looks as follows

    .. code-block:: none

                    +--------+
             +------+ switch +-----+
             |      +--------+     |
          +--+-+                 +-+--+
        +-|eth0|-+          +----|eth0|-----+
        | +----+ |          |    +--+-+     |
        | host1  |          | host2 |       |
        +--------+          |     +-+--+    |
                            |   +-|veth|--+ |
                            |   | +----+  | |
                            |   | host2ns | |
                            |   +---------+ |
                            +---------------+

    This is a derived class from SimpleNetworkRecipe which creates a netns on
    the second host, enables forwarding into it and returns it as second
    endpoint. Perf and ping tests will therefore excercise the second host's
    routing path.
    """
    netns_ipv4 = IPv4NetworkParam(default="192.168.102.0/24")
    netns_ipv6 = IPv6NetworkParam(default="fc00:1::/64")

    def test_wide_configuration(self, config):
        """
        Test wide configuration for this recipe consists of:
        - Creating the netns on host2, named 'host2ns'
        - Adding a veth pair pn0 and np0, the latter sits inside the netns
          - host2.pn0    = 192.168.102.1/24 and fc00:1::1/64
          - host2.ns.np0 = 192.168.102.2/24 and fc00:1::2/64
        - Add routes inside the netns and on host1
        """
        host1 = self.matched.host1
        host2 = self.matched.host2
        config = super().test_wide_configuration(config)

        host2.ns = NetNamespace("host2ns")

        host2.pn0, host2.np0 = VethPair()
        host2.ns.np0 = host2.np0

        ipv4_addr = interface_addresses(self.params.netns_ipv4)
        ipv6_addr = interface_addresses(self.params.netns_ipv6)
        config.configure_and_track_ip(host2.pn0, next(ipv4_addr))
        config.configure_and_track_ip(host2.pn0, next(ipv6_addr))
        config.configure_and_track_ip(host2.ns.np0, next(ipv4_addr))
        config.configure_and_track_ip(host2.ns.np0, next(ipv6_addr))
        host2.pn0.up_and_wait()
        host2.ns.np0.up_and_wait()

        for gw in (self.params.netns_ipv4[1], self.params.netns_ipv6[1]):
            host2.ns.run(f"ip route add default via {gw}")

        host2.run("sysctl -w net.ipv4.ip_forward=1")
        host2.run("sysctl -w net.ipv6.conf.all.forwarding=1")

        for dst, gw in [(self.params.netns_ipv4[2], self.params.net_ipv4[2]),
                        (self.params.netns_ipv6[2], self.params.net_ipv6[2])]:
            host1.run(f"ip route add {dst} via {gw}")

        return config

    def test_wide_deconfiguration(self, config):
        config = super().test_wide_deconfiguration(config)
        self.matched.host2.run("sysctl -w net.ipv4.ip_forward=0")
        self.matched.host2.run("sysctl -w net.ipv6.conf.all.forwarding=0")

    def generate_ping_endpoints(self, config):
        return [PingEndpoints(self.matched.host1.eth0,
                              self.matched.host2.ns.np0)]

    def generate_perf_endpoints(self, config: EnrtConfiguration) -> list[Collection[EndpointPair[IPEndpoint]]]:
        return [ip_endpoint_pairs(config, (self.matched.host1.eth0,
                                           self.matched.host2.ns.np0))]
