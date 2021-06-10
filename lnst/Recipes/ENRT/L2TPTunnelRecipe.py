from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Common.IpAddress import AF_INET, AF_INET6
from lnst.Common.Parameters import ChoiceParam, StrParam
from lnst.RecipeCommon.L2TPManager import L2TPManager
from lnst.Devices import L2TPSessionDevice
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.RecipeCommon.PacketAssert import PacketAssertConf
from lnst.Recipes.ENRT.BaseTunnelRecipe import BaseTunnelRecipe
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin,
)


class L2TPTunnelRecipe(CommonHWSubConfigMixin, BaseTunnelRecipe):
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

    def configure_underlying_network(self, configuration):
        """
        The underlying network for the tunnel consists of the Ethernet
        devices on the matched hosts.
        """
        host1 = self.matched.host1
        host2 = self.matched.host2

        for i, device in enumerate([host1.eth0, host2.eth0]):
            if self.params.carrier_ipversion == "ipv4":
                device.ip_add("192.168.200." + str(i + 1) + "/24")
            else:
                device.ip_add("fc00::" + str(i + 1) + "/64")

            device.up()
            configuration.test_wide_devices.append(device)

        self.wait_tentative_ips(configuration.test_wide_devices)
        configuration.tunnel_endpoints = (host1.eth0, host2.eth0)

    def create_tunnel(self, configuration):
        """
        One L2TP tunnel is configured on both hosts using the
        :any:`L2TPManager`. Each host configures one L2TP session for the
        tunnel. IPv4 addresses are assigned to the l2tp session devices.
        """
        endpoint1, endpoint2 = configuration.tunnel_endpoints
        host1 = endpoint1.netns
        host2 = endpoint2.netns
        if self.params.carrier_ipversion == "ipv4":
            ip_filter = {"family": AF_INET}
        else:
            ip_filter = {"family": AF_INET6, "is_link_local": False}

        endpoint1_ip = endpoint1.ips_filter(**ip_filter)[0]
        endpoint2_ip = endpoint2.ips_filter(**ip_filter)[0]

        for host in [host1, host2]:
            host.run("modprobe l2tp_eth")

        host1.l2tp = host1.init_class(L2TPManager)
        host2.l2tp = host2.init_class(L2TPManager)

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

        ip1 = "10.42.1.1/8"
        ip2 = "10.42.1.2/8"
        host1.l2tp_session1.ip_add(ip1, peer=ip2)
        host2.l2tp_session1.ip_add(ip2, peer=ip1)

        configuration.tunnel_devices.extend([host1.l2tp_session1, host2.l2tp_session1])

    def test_wide_deconfiguration(self, config):
        for host in [self.matched.host1, self.matched.host2]:
            host.l2tp.cleanup()

        super().test_wide_deconfiguration(config)

    def generate_ping_endpoints(self, config):
        """
        The ping endpoints for this recipe are simply the tunnel endpoints

        Returned as::

            [PingEndpoints(self.matched.host1.l2tp_session1, self.matched.host2.l2tp_session1)]
        """
        return [
            PingEndpoints(
                self.matched.host1.l2tp_session1, self.matched.host2.l2tp_session1
            )
        ]

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
