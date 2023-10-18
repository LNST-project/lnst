from collections.abc import Iterator
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Common.IpAddress import (
    AF_INET,
    AF_INET6,
    Ip4Address,
    interface_addresses,
)
from lnst.Common.Parameters import (
    StrParam,
    ChoiceParam,
    IPv4NetworkParam,
    IPv6NetworkParam,
)
from lnst.RecipeCommon.L2TPManager import L2TPManager
from lnst.Devices import L2TPSessionDevice, RemoteDevice
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpointPair
from lnst.RecipeCommon.PacketAssert import PacketAssertConf
from lnst.Recipes.ENRT.BaseTunnelRecipe import BaseTunnelRecipe
from lnst.Recipes.ENRT.EnrtConfiguration import EnrtConfiguration
from lnst.Recipes.ENRT.ConfigMixins.PauseFramesHWConfigMixin import (
    PauseFramesHWConfigMixin,
)
from lnst.Recipes.ENRT.helpers import ping_endpoint_pairs


class L2TPTunnelRecipe(PauseFramesHWConfigMixin, BaseTunnelRecipe):
    """
    This class implements a recipe that configures a simple L2TP tunnel with
    one tunnel session between two hosts.

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
         |  L2TP tunnel |      |  L2TPtunnel  |
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

        :param l2tp_encapsulation:
            (mandatory test parameter) the encapsulation mode for the L2TP tunnel,
            can be either **udp** or **ip**
    """

    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    carrier_ipversion = ChoiceParam(type=StrParam, choices=set(["ipv4", "ipv6"]))
    l2tp_encapsulation = ChoiceParam(
        type=StrParam, choices=set(["udp", "ip"]), mandatory=True
    )

    net_ipv4 = IPv4NetworkParam(default="192.168.200.0/24")
    net_ipv6 = IPv6NetworkParam(default="fc00::/64")

    def configure_underlying_network(self, config: EnrtConfiguration) -> tuple[RemoteDevice, RemoteDevice]:
        """
        The underlying network for the tunnel consists of the Ethernet
        devices on the matched hosts.
        """
        host1 = self.matched.host1
        host2 = self.matched.host2

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
        One L2TP tunnel is configured on both hosts using the
        :any:`L2TPManager`. Each host configures one L2TP session for the
        tunnel. IPv4 addresses are assigned to the l2tp session devices.
        """
        host1 = self.matched.host1
        host2 = self.matched.host2

        for host in [host1, host2]:
            host.run("modprobe l2tp_eth")

        host1.l2tp = host1.init_class(L2TPManager)
        host2.l2tp = host2.init_class(L2TPManager)

        endpoint1, endpoint2 = tunnel_endpoints
        endpoint1_ip = config.ips_for_device(endpoint1)[0]
        endpoint2_ip = config.ips_for_device(endpoint2)[0]

        self.wait_tentative_ips(tunnel_endpoints)
        host1.l2tp.create_tunnel(
            tunnel_id=1000,
            peer_tunnel_id=1000,
            encap=self.params.l2tp_encapsulation,
            local=str(endpoint1_ip),
            remote=str(endpoint2_ip),
            udp_sport=5000,
            udp_dport=5000,
        )
        host2.l2tp.create_tunnel(
            tunnel_id=1000,
            peer_tunnel_id=1000,
            encap=self.params.l2tp_encapsulation,
            local=str(endpoint2_ip),
            remote=str(endpoint1_ip),
            udp_sport=5000,
            udp_dport=5000,
        )
        host1.l2tp_session1 = L2TPSessionDevice(
            tunnel_id=1000,
            session_id=2000,
            peer_session_id=2000,
        )
        host2.l2tp_session1 = L2TPSessionDevice(
            tunnel_id=1000,
            session_id=2000,
            peer_session_id=2000,
        )

        for device in [host1.l2tp_session1, host2.l2tp_session1]:
            device.up()

        ip1 = Ip4Address("10.42.1.1/8")
        ip2 = Ip4Address("10.42.1.2/8")
        config.configure_and_track_ip(host1.l2tp_session1, ip1, peer=ip2)
        config.configure_and_track_ip(host2.l2tp_session1, ip2, peer=ip1)

        return (host1.l2tp_session1, host2.l2tp_session1)

    def test_wide_deconfiguration(self, config):
        for host in [self.matched.host1, self.matched.host2]:
            host.l2tp.cleanup()

        super().test_wide_deconfiguration(config)

    def generate_ping_endpoints(self, config: EnrtConfiguration) -> Iterator[PingEndpointPair]:
        """
        The ping endpoints for this recipe are simply the tunnel endpoints
        """
        yield from ping_endpoint_pairs(config, (self.matched.host1.l2tp_session1, self.matched.host2.l2tp_session1))

    def get_packet_assert_config(self, ping_config):
        pa_kwargs = {}

        if self.params.carrier_ipversion == "ipv4":
            ip_filter = {"family": AF_INET}
        else:
            ip_filter = {"family": AF_INET6, "is_link_local": False}

        m1_carrier = self.matched.host1.eth0
        m2_carrier = self.matched.host2.eth0
        m1_carrier_ip = m1_carrier.ips_filter(**ip_filter)[0]
        m2_carrier_ip = m2_carrier.ips_filter(**ip_filter)[0]

        """
        encap udp: IP 192.168.200.1.5000 > 192.168.200.2.5000: UDP
        encap ip: 192.168.200.1 > 192.168.200.2:  ip-proto-115 106
        """

        if self.params.l2tp_encapsulation == "ip":
            pa_kwargs["p_filter"] = "{} proto 115".format(
                "ip" if self.params.carrier_ipversion == "ipv4" else "ip6",
            )
            grep_pattern = "{} {} > {}:[ ]*ip-proto-115".format(
                "IP" if self.params.carrier_ipversion == "ipv4" else "IP6",
                m1_carrier_ip,
                m2_carrier_ip,
            )
        elif self.params.l2tp_encapsulation == "udp":
            pa_kwargs["p_filter"] = "udp"
            grep_pattern = "{} {}.[0-9]+ > {}.[0-9]+:[ ]*UDP".format(
                "IP" if self.params.carrier_ipversion == "ipv4" else "IP6",
                m1_carrier_ip,
                m2_carrier_ip,
            )

        pa_kwargs["grep_for"] = [grep_pattern]
        if ping_config.count:
            pa_kwargs["p_min"] = ping_config.count
        m2 = ping_config.destination
        pa_config = PacketAssertConf(m2, m2_carrier, **pa_kwargs)

        return pa_config

    @property
    def pause_frames_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
