from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Common.IpAddress import (
    AF_INET,
    AF_INET6,
    Ip4Address,
    Ip6Address,
    interface_addresses,
)
from lnst.Devices import GeneveDevice
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.RecipeCommon.PacketAssert import PacketAssertConf
from lnst.Common.Parameters import (
    Param,
    StrParam,
    ChoiceParam,
    IPv4NetworkParam,
    IPv6NetworkParam,
)
from lnst.Recipes.ENRT.BaseTunnelRecipe import BaseTunnelRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.PauseFramesHWConfigMixin import (
    PauseFramesHWConfigMixin,
)


class GeneveTunnelRecipe(
    PauseFramesHWConfigMixin, OffloadSubConfigMixin, BaseTunnelRecipe
):
    """
    This class implements a recipe that configures a simple Geneve tunnel
    between two hosts.

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
         |  gnv tunnel  |      |  gnv tunnel  |
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

    carrier_ipversion = ChoiceParam(type=StrParam, choices=set(["ipv4", "ipv6"]))
    net_ipv4 = IPv4NetworkParam(default="192.168.101.0/24")
    net_ipv6 = IPv6NetworkParam(default="fc00::/64")

    def configure_underlying_network(self, configuration):
        """
        The underlying network for the tunnel consists of the Ethernet
        devices on the matched hosts.
        """
        host1, host2 = self.matched.host1, self.matched.host2
        ipv4_addr = interface_addresses(self.params.net_ipv4)
        ipv6_addr = interface_addresses(self.params.net_ipv6)
        for device in [host1.eth0, host2.eth0]:
            if self.params.carrier_ipversion == "ipv4":
                device.ip_add(next(ipv4_addr))
            else:
                device.ip_add(next(ipv6_addr))
            device.up()
            configuration.test_wide_devices.append(device)

        self.wait_tentative_ips(configuration.test_wide_devices)
        configuration.tunnel_endpoints = (host1.eth0, host2.eth0)

    def create_tunnel(self, configuration):
        """
        The Geneve tunnel devices are configured with IPv4 and IPv6 addresses.
        """
        endpoint1, endpoint2 = configuration.tunnel_endpoints
        m1 = endpoint1.netns
        m2 = endpoint2.netns
        if self.params.carrier_ipversion == "ipv4":
            ip_filter = {"family": AF_INET}
        else:
            ip_filter = {"family": AF_INET6, "is_link_local": False}

        endpoint1_ip = endpoint1.ips_filter(**ip_filter)[0]
        endpoint2_ip = endpoint2.ips_filter(**ip_filter)[0]

        a_ip4 = Ip4Address("20.0.0.10/8")
        b_ip4 = Ip4Address("20.0.0.20/8")

        a_ip6 = Ip6Address("fee0::10/64")
        b_ip6 = Ip6Address("fee0::20/64")

        m1.gnv_tunnel = GeneveDevice(remote=endpoint2_ip, id=1234)
        m2.gnv_tunnel = GeneveDevice(remote=endpoint1_ip, id=1234)

        # A
        m1.gnv_tunnel.mtu = 1400
        m1.gnv_tunnel.up()
        m1.gnv_tunnel.ip_add(a_ip4)
        m1.gnv_tunnel.ip_add(a_ip6)

        # B
        m2.gnv_tunnel.mtu = 1400
        m2.gnv_tunnel.up()
        m2.gnv_tunnel.ip_add(b_ip4)
        m2.gnv_tunnel.ip_add(b_ip6)

        configuration.tunnel_devices.extend([m1.gnv_tunnel, m2.gnv_tunnel])
        self.wait_tentative_ips(configuration.tunnel_devices)

    def generate_ping_endpoints(self, config):
        """
        The ping endpoints for this recipe are simply the tunnel endpoints

        Returned as::

            [PingEndpoints(self.matched.host1.gnv_tunnel, self.matched.host2.gnv_tunnel)]
        """
        return [
            PingEndpoints(self.matched.host1.gnv_tunnel, self.matched.host2.gnv_tunnel)
        ]

    def get_packet_assert_config(self, ping_config):
        """
        The packet assert test configuration contains filter for ip6 protocol
        and grep patterns to match the ICMP or ICMP6 echo requests encapsulated
        by Geneve.
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
        if self.params.carrier_ipversion == "ipv4":
            pa_kwargs["p_filter"] = "ip host {}".format(m1_carrier_ip)
            grep_pattern = "IP "
        else:
            pa_kwargs["p_filter"] = "ip6"
            grep_pattern = "IP6 "

        grep_pattern += "{}\.[0-9]+ > {}\.[0-9]+: Geneve.*vni 0x4d2: ".format(
            m1_carrier_ip, m2_carrier_ip
        )

        if isinstance(ip2, Ip4Address):
            grep_pattern += "IP {} > {}: ICMP".format(ip1, ip2)
        elif isinstance(ip2, Ip6Address):
            grep_pattern += "IP6 {} > {}: ICMP6".format(ip1, ip2)

        pa_kwargs["grep_for"] = [grep_pattern]

        if ping_config.count:
            pa_kwargs["p_min"] = ping_config.count
        m2 = ping_config.destination
        pa_config = PacketAssertConf(m2, m2_carrier, **pa_kwargs)

        return pa_config

    @property
    def offload_nics(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def pause_frames_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
