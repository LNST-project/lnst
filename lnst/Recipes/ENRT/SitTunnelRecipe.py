from collections.abc import Iterator
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Common.IpAddress import (
    AF_INET,
    Ip4Address,
    Ip6Address,
    interface_addresses,
)
from lnst.Devices import SitDevice, RemoteDevice
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpointPair
from lnst.RecipeCommon.PacketAssert import PacketAssertConf
from lnst.Common.Parameters import (
    StrParam,
    ChoiceParam,
    IPv4NetworkParam,
)
from lnst.Recipes.ENRT.BaseTunnelRecipe import BaseTunnelRecipe
from lnst.Recipes.ENRT.EnrtConfiguration import EnrtConfiguration
from lnst.Recipes.ENRT.ConfigMixins.MTUHWConfigMixin import MTUHWConfigMixin
from lnst.Recipes.ENRT.ConfigMixins.PauseFramesHWConfigMixin import (
    PauseFramesHWConfigMixin,
)
from lnst.Recipes.ENRT.helpers import ping_endpoint_pairs


class SitTunnelRecipe(MTUHWConfigMixin, PauseFramesHWConfigMixin, BaseTunnelRecipe):
    """
    This class implements a recipe that configures a simple SIT tunnel between
    two hosts.

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
         |  sit tunnel  |      |  sit tunnel  |
         |  ----------  |      |  ----------  |
         |              |      |              |
         |    host1     |      |    host2     |
         '--------------'      '--------------'

    The actual test machinery is implemented in the :any:`BaseEnrtRecipe` class.

    The test wide configuration is implemented in the :any:`BaseTunnelRecipe`
    class.

    The recipe provides additional parameter:

        :param tunnel_mode:
            this parameter specifies the mode of the SIT tunnel, can be any of
            the **any**, **ip6ip6**, **ipip** or **mplsip**
    """

    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    tunnel_mode = ChoiceParam(
        type=StrParam, choices=set(["any", "ip6ip", "ipip", "mplsip"]), mandatory=True
    )
    net_ipv4 = IPv4NetworkParam(default="192.168.101.0/24")

    def configure_underlying_network(self, config: EnrtConfiguration) -> tuple[RemoteDevice, RemoteDevice]:
        """
        The underlying network for the tunnel consists of the Ethernet
        devices on the matched hosts.
        """
        host1, host2 = self.matched.host1, self.matched.host2
        ipv4_addr = interface_addresses(self.params.net_ipv4)
        for device in [host1.eth0, host2.eth0]:
            config.configure_and_track_ip(device, next(ipv4_addr))
            device.up()

        return (host1.eth0, host2.eth0)

    def create_tunnel(
        self,
        config: EnrtConfiguration,
        tunnel_endpoints: tuple[RemoteDevice, RemoteDevice],
    ) -> tuple[RemoteDevice, RemoteDevice]:
        """
        The SIT tunnel devices are configured with IPv4 and IPv6 addresses
        of individual networks. Routes are configured accordingly.
        """
        endpoint1, endpoint2 = tunnel_endpoints
        m1 = endpoint1.netns
        m2 = endpoint2.netns
        endpoint1_ip = config.ips_for_device(endpoint1)[0]
        endpoint2_ip = config.ips_for_device(endpoint2)[0]

        a_ip4 = Ip4Address("192.168.6.2/24")
        a_net4 = "192.168.6.0/24"
        b_ip4 = Ip4Address("192.168.7.2/24")
        b_net4 = "192.168.7.0/24"

        a_ip6 = Ip6Address("6001:db8:ac10:fe01::2/64")
        a_net6 = "6001:db8:ac10:fe01::0/64"
        b_ip6 = Ip6Address("7001:db8:ac10:fe01::2/64")
        b_net6 = "7001:db8:ac10:fe01::0/64"

        m1.sit_tunnel = SitDevice(
            local=endpoint1_ip, remote=endpoint2_ip, mode=self.params.tunnel_mode
        )
        m2.sit_tunnel = SitDevice(
            local=endpoint2_ip, remote=endpoint1_ip, mode=self.params.tunnel_mode
        )

        # A
        m1.sit_tunnel.up()
        config.configure_and_track_ip(m1.sit_tunnel, a_ip4)
        config.configure_and_track_ip(m1.sit_tunnel, a_ip6)
        m1.run("ip -4 route add {} dev {}".format(b_net4, m1.sit_tunnel.name))
        m1.run("ip -6 route add {} dev {}".format(b_net6, m1.sit_tunnel.name))

        # B
        m2.sit_tunnel.up()
        config.configure_and_track_ip(m2.sit_tunnel, b_ip4)
        config.configure_and_track_ip(m2.sit_tunnel, b_ip6)
        m2.run("ip -4 route add {} dev {}".format(a_net4, m2.sit_tunnel.name))
        m2.run("ip -6 route add {} dev {}".format(a_net6, m2.sit_tunnel.name))

        return (m1.sit_tunnel, m2.sit_tunnel)

    def generate_ping_endpoints(self, config: EnrtConfiguration) -> Iterator[PingEndpointPair]:
        """
        The ping endpoints for this recipe are simply the tunnel endpoints
        """
        yield from ping_endpoint_pairs(config, (self.matched.host1.sit_tunnel, self.matched.host2.sit_tunnel))

    def get_packet_assert_config(self, ping_config):
        """
        The packet assert test configuration contains filter for ip6 protocol
        and grep patterns to match the ICMP or ICMP6 echo requests encapsulated
        by SIT.
        """
        ip_filter = {"family": AF_INET}
        m1_carrier = self.matched.host1.eth0
        m2_carrier = self.matched.host2.eth0
        m1_carrier_ip = m1_carrier.ips_filter(**ip_filter)[0]
        m2_carrier_ip = m2_carrier.ips_filter(**ip_filter)[0]

        ip1 = ping_config.client_bind
        ip2 = ping_config.destination_address

        pa_kwargs = {}
        pa_kwargs["p_filter"] = "ip host {}".format(m1_carrier_ip)

        # TODO: handle mplsip mode
        if isinstance(ip2, Ip4Address):
            grep_pattern = [
                "IP {} > {}: IP {} > {}: ICMP".format(
                    m1_carrier_ip, m2_carrier_ip, ip1, ip2
                )
            ]

        elif isinstance(ip2, Ip6Address):
            grep_pattern = [
                "IP {} > {}: IP6 {} > {}: ICMP6".format(
                    m1_carrier_ip, m2_carrier_ip, ip1, ip2
                )
            ]

        pa_kwargs["grep_for"] = grep_pattern

        if ping_config.count:
            pa_kwargs["p_min"] = ping_config.count
        m2 = ping_config.destination
        pa_config = PacketAssertConf(m2, m2_carrier, **pa_kwargs)

        return pa_config

    @property
    def pause_frames_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.sit_tunnel, self.matched.host2.sit_tunnel]
