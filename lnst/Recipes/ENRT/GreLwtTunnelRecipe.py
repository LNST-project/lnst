from collections.abc import Iterator
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Common.IpAddress import (
    AF_INET,
    AF_INET6,
    ipaddress,
    Ip4Address,
    Ip6Address,
    interface_addresses,
)
from lnst.Devices import GreDevice, LoopbackDevice, RemoteDevice
from lnst.RecipeCommon.PacketAssert import PacketAssertConf
from lnst.Common.Parameters import (
    Param,
    StrParam,
    ChoiceParam,
    IPv4NetworkParam,
    IPv6NetworkParam,
)
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpointPair
from lnst.Recipes.ENRT.BaseTunnelRecipe import BaseTunnelRecipe
from lnst.Recipes.ENRT.EnrtConfiguration import EnrtConfiguration
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.Recipes.ENRT.helpers import ip_endpoint_pairs, ping_endpoint_pairs
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.PauseFramesHWConfigMixin import (
    PauseFramesHWConfigMixin,
)


class GreLwtTunnelRecipe(
    PauseFramesHWConfigMixin, OffloadSubConfigMixin, BaseTunnelRecipe
):
    """
    This class implements a recipe that configures a simple Gre lightweight
    tunnel between two hosts.

    .. code-block:: none

                        .--------.
                 .------| switch |-----.
                 |      '--------'     |
                 |                     |
         .-------|------.      .-------|------.
         |    .--'-.    |      |    .--'-.    |
         |    |eth0|    |      |    |eth0|    |
         |    '----'    |      |    '----'    |
         |      | |     |      |      | |     |
         |  ----' '---  |      |  ----' '---  |
         |  gre tunnel  |      |  gre tunnel  |
         |  ----------  |      |  ----------  |
         |              |      |              |
         |    host1     |      |    host2     |
         '--------------'      '--------------'

    The actual test machinery is implemented in the :any:`BaseEnrtRecipe` class.

    The test wide configuration is implemented in the :any:`BaseTunnelRecipe`
    class.

    The recipe provides additional parameter:

        :param carrier_ipversion:
            This parameter specifies whether IPv4 or IPv6 addresses are
            used for the underlying (carrier) network. The value is either
            **ipv4** or **ipv6**
    """

    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    offload_combinations = Param(
        default=(
            dict(gro="on", gso="on", tso="on"),
            dict(gro="off", gso="on", tso="on"),
            dict(gro="on", gso="off", tso="off"),
            dict(gro="on", gso="on", tso="off"),
        )
    )

    # TODO: ping over IPv6 does not work yet
    ip_versions = Param(default=("ipv4",))
    carrier_ipversion = ChoiceParam(type=StrParam, choices=set(["ipv4", "ipv6"]))
    net_ipv4 = IPv4NetworkParam(default="192.168.101.0/24")
    net_ipv6 = IPv6NetworkParam(default="fc00::/64")

    def configure_underlying_network(self, config: EnrtConfiguration) -> tuple[RemoteDevice, RemoteDevice]:
        """
        The underlying network for the tunnel consists of the Ethernet
        devices on the matched hosts.
        """
        host1, host2 = self.matched.host1, self.matched.host2
        ipv4_addr = interface_addresses(self.params.net_ipv4)
        ipv6_addr = interface_addresses(self.params.net_ipv6)
        for device in [host1.eth0, host2.eth0]:
            if self.params.carrier_ipversion == "ipv4":
                config.configure_and_track_ip(device, next(ipv4_addr))
            else:
                config.configure_and_track_ip(device, next(ipv6_addr))
            device.up()

        return (host1.eth0, host2.eth0)

    def create_tunnel(
        self,
        config: EnrtConfiguration,
        tunnel_endpoints: tuple[RemoteDevice, RemoteDevice],
    ) -> tuple[RemoteDevice, RemoteDevice]:
        """
        The Gre tunnel devices are created with external flag specified
        so that the encapsulation can be defined externally by routes.

        Routes for IPv4 and IPv6 networks to be tunneled through the Gre are
        added.

        IPv4 and IPv6 addresses of the tunneled networks are configured on
        the loopback devices of the matched hosts.
        """
        endpoint1, endpoint2 = tunnel_endpoints
        m1 = endpoint1.netns
        m2 = endpoint2.netns

        endpoint1_ip = config.ips_for_device(endpoint1)[0]
        endpoint2_ip = config.ips_for_device(endpoint2)[0]

        m1_dummy_ip = ipaddress("172.16.10.1/32")
        m1_dummy_ip6 = ipaddress("fc00:a::1/128")
        m2_dummy_ip = ipaddress("172.16.20.1/32")
        m2_dummy_ip6 = ipaddress("fc00:b::1/128")

        m1.gre_tunnel = GreDevice(external=True)
        m2.gre_tunnel = GreDevice(external=True)
        m1.lo = LoopbackDevice()
        m2.lo = LoopbackDevice()

        # A
        config.configure_and_track_ip(m1.lo, m1_dummy_ip)
        config.configure_and_track_ip(m1.lo, m1_dummy_ip6)
        m1.gre_tunnel.mtu = 1400
        m1.gre_tunnel.up()

        # B
        config.configure_and_track_ip(m2.lo, m2_dummy_ip)
        config.configure_and_track_ip(m2.lo, m2_dummy_ip6)
        m2.gre_tunnel.mtu = 1400
        m2.gre_tunnel.up()

        tunnel_id = 1234
        encap = "ip" if self.params.carrier_ipversion == "ipv4" else "ip6"
        m1.run(
            "ip route add {} encap {} id {} dst {} dev {}".format(
                m2_dummy_ip, encap, tunnel_id, endpoint2_ip, m1.gre_tunnel.name
            )
        )
        m2.run(
            "ip route add {} encap {} id {} dst {} dev {}".format(
                m1_dummy_ip, encap, tunnel_id, endpoint1_ip, m2.gre_tunnel.name
            )
        )
        m1.run(
            "ip route add {} encap {} id {} dst {} dev {}".format(
                m2_dummy_ip6, encap, tunnel_id, endpoint2_ip, m1.gre_tunnel.name
            )
        )
        m2.run(
            "ip route add {} encap {} id {} dst {} dev {}".format(
                m1_dummy_ip6, encap, tunnel_id, endpoint1_ip, m2.gre_tunnel.name
            )
        )

        return (m1.gre_tunnel, m2.gre_tunnel)

    def generate_ping_endpoints(self, config: EnrtConfiguration) -> Iterator[list[PingEndpointPair]]:
        """
        The ping endpoints for this recipe are the loopback devices that
        are configured with IP addresses of the tunnelled networks.
        """
        yield ping_endpoint_pairs(config, (self.matched.host1.lo, self.matched.host2.lo))

    def get_packet_assert_config(self, ping_config):
        """
        The packet assert test configuration contains filter for gre protocol
        and grep patterns to match the ICMP or ICMP6 echo requests encapsulated
        by Gre.
        """
        if self.params.carrier_ipversion == "ipv4":
            ip_filter = {"family": AF_INET}
        else:
            ip_filter = {"family": AF_INET6, "is_link_local": False}

        m1_carrier = self.matched.host1.eth0
        m2_carrier = self.matched.host2.eth0
        m1_carrier_ip = m1_carrier.ips_filter(**ip_filter)[0]
        m2_carrier_ip = m2_carrier.ips_filter(**ip_filter)[0]

        ip1 = ping_config.client_bind
        ip2 = ping_config.destination_address

        pa_kwargs = {}
        pa_kwargs["p_filter"] = "proto gre"

        if isinstance(ip2, Ip4Address):
            pat1 = "{} > {}: GREv0, .* IP {} > {}: ICMP echo request".format(
                m1_carrier_ip, m2_carrier_ip, ip1, ip2
            )
            pat2 = "{} > {}: GREv0 \| {} > {}: ICMP echo request".format(
                m1_carrier_ip, m2_carrier_ip, ip1, ip2
            )
            grep_pattern = ["({})|({})".format(pat1, pat2)]
        elif isinstance(ip2, Ip6Address):
            pat1 = "{} > {}: GREv0, .* IP6 {} > {}: ICMP6, echo request".format(
                m1_carrier_ip, m2_carrier_ip, ip1, ip2
            )
            pat2 = "{} > {}: GREv0 \| {} > {}: ICMP6, echo request".format(
                m1_carrier_ip, m2_carrier_ip, ip1, ip2
            )
            grep_pattern = ["({})|({})".format(pat1, pat2)]
        else:
            raise Exception("The destination address is nor IPv4 or IPv6 address")

        pa_kwargs["grep_for"] = grep_pattern

        if ping_config.count:
            pa_kwargs["p_min"] = ping_config.count
        m2 = ping_config.destination
        pa_config = PacketAssertConf(m2, m2_carrier, **pa_kwargs)

        return pa_config

    def generate_perf_endpoints(self, config: EnrtConfiguration) -> Iterator[list[EndpointPair[IPEndpoint]]]:
        """
        The perf endpoints for this recipe are the loopback devices that
        are configured with IP addresses of the tunnelled networks.
        """
        yield ip_endpoint_pairs(config, (self.matched.host1.lo, self.matched.host2.lo))

    @property
    def offload_nics(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def pause_frames_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
