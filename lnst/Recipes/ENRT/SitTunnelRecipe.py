from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Common.IpAddress import (
    AF_INET,
    ipaddress,
    Ip4Address,
    Ip6Address,
)
from lnst.Devices import SitDevice
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.RecipeCommon.PacketAssert import PacketAssertConf
from lnst.Common.Parameters import StrParam, ChoiceParam
from lnst.Recipes.ENRT.BaseTunnelRecipe import BaseTunnelRecipe


class SitTunnelRecipe(BaseTunnelRecipe):
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

    def configure_underlying_network(self, configuration):
        """
        The underlying network for the tunnel consists of the Ethernet
        devices on the matched hosts.
        """
        host1, host2 = self.matched.host1, self.matched.host2
        for i, device in enumerate([host1.eth0, host2.eth0]):
            device.ip_add(ipaddress("192.168.101." + str(i + 1) + "/24"))
            device.up()
            configuration.test_wide_devices.append(device)

        configuration.tunnel_endpoints = (host1.eth0, host2.eth0)

    def create_tunnel(self, configuration):
        """
        The SIT tunnel devices are configured with IPv4 and IPv6 addresses
        of individual networks. Routes are configured accordingly.
        """
        endpoint1, endpoint2 = configuration.tunnel_endpoints
        m1 = endpoint1.netns
        m2 = endpoint2.netns
        ip_filter = {"family": AF_INET}
        endpoint1_ip = endpoint1.ips_filter(**ip_filter)[0]
        endpoint2_ip = endpoint2.ips_filter(**ip_filter)[0]

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
        m1.sit_tunnel.ip_add(a_ip4)
        m1.sit_tunnel.ip_add(a_ip6)
        m1.run("ip -4 route add {} dev {}".format(b_net4, m1.sit_tunnel.name))
        m1.run("ip -6 route add {} dev {}".format(b_net6, m1.sit_tunnel.name))

        # B
        m2.sit_tunnel.up()
        m2.sit_tunnel.ip_add(b_ip4)
        m2.sit_tunnel.ip_add(b_ip6)
        m2.run("ip -4 route add {} dev {}".format(a_net4, m2.sit_tunnel.name))
        m2.run("ip -6 route add {} dev {}".format(a_net6, m2.sit_tunnel.name))

        configuration.tunnel_devices.extend([m1.sit_tunnel, m2.sit_tunnel])
        self.wait_tentative_ips(configuration.tunnel_devices)

    def generate_ping_endpoints(self, config):
        """
        The ping endpoints for this recipe are simply the tunnel endpoints

        Returned as::

            [PingEndpoints(self.matched.host1.sit_tunnel, self.matched.host2.sit_tunnel)]
        """
        return [
            PingEndpoints(self.matched.host1.sit_tunnel, self.matched.host2.sit_tunnel)
        ]

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
