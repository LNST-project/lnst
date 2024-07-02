from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Common.IpAddress import (
    AF_INET,
    AF_INET6,
    Ip4Address,
    Ip6Address,
    interface_addresses,
)
from lnst.Devices import GeneveDevice, RemoteDevice
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
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import CommonHWSubConfigMixin
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin,
)


class GeneveTunnelRecipe(
    CommonHWSubConfigMixin, OffloadSubConfigMixin, BaseTunnelRecipe
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
            device.up_and_wait()

        return (host1.eth0, host2.eth0)

    def create_tunnel(
        self,
        config: EnrtConfiguration,
        tunnel_endpoints: tuple[RemoteDevice, RemoteDevice],
    ) -> tuple[RemoteDevice, RemoteDevice]:
        """
        The Geneve tunnel devices are configured with IPv4 and IPv6 addresses.
        """
        endpoint1, endpoint2 = tunnel_endpoints
        m1 = endpoint1.netns
        m2 = endpoint2.netns

        endpoint1_ip = config.ips_for_device(endpoint1)[0]
        endpoint2_ip = config.ips_for_device(endpoint2)[0]

        a_ip4 = Ip4Address("20.0.0.10/8")
        b_ip4 = Ip4Address("20.0.0.20/8")

        a_ip6 = Ip6Address("fee0::10/64")
        b_ip6 = Ip6Address("fee0::20/64")

        m1.gnv_tunnel = GeneveDevice(remote=endpoint2_ip, id=1234)
        m2.gnv_tunnel = GeneveDevice(remote=endpoint1_ip, id=1234)

        # A
        m1.gnv_tunnel.mtu = 1400
        m1.gnv_tunnel.up_and_wait()
        config.configure_and_track_ip(m1.gnv_tunnel, a_ip4)
        config.configure_and_track_ip(m1.gnv_tunnel, a_ip6)

        # B
        m2.gnv_tunnel.mtu = 1400
        m2.gnv_tunnel.up_and_wait()
        config.configure_and_track_ip(m2.gnv_tunnel, b_ip4)
        config.configure_and_track_ip(m2.gnv_tunnel, b_ip6)

        return (m1.gnv_tunnel, m2.gnv_tunnel)

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
            grep_pattern = r"IP "
        else:
            pa_kwargs["p_filter"] = "ip6"
            grep_pattern = r"IP6 "

        grep_pattern += r"{}\.[0-9]+ > {}\.[0-9]+: Geneve.*vni 0x4d2: ".format(
            m1_carrier_ip, m2_carrier_ip
        )

        if isinstance(ip2, Ip4Address):
            grep_pattern += r"IP {} > {}: ICMP".format(ip1, ip2)
        elif isinstance(ip2, Ip6Address):
            grep_pattern += r"IP6 {} > {}: ICMP6".format(ip1, ip2)

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

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.gnv_tunnel, self.matched.host2.gnv_tunnel]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
