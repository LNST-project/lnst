from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Common.IpAddress import (
    AF_INET6,
    ipaddress,
    interface_addresses,
)
from lnst.Devices import Ip6TnlDevice
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.RecipeCommon.PacketAssert import PacketAssertConf
from lnst.Common.Parameters import (
    StrParam,
    ChoiceParam,
    IPv6NetworkParam,
)
from lnst.Recipes.ENRT.BaseTunnelRecipe import BaseTunnelRecipe
from lnst.Recipes.ENRT.ConfigMixins.MTUHWConfigMixin import MTUHWConfigMixin
from lnst.Recipes.ENRT.ConfigMixins.PauseFramesHWConfigMixin import (
    PauseFramesHWConfigMixin,
)


class Ip6TnlTunnelRecipe(MTUHWConfigMixin, PauseFramesHWConfigMixin, BaseTunnelRecipe):
    """
    This class implements a recipe that configures a simple Ip6Tnl tunnel between
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
         | ip6tnl tunnel|      | ip6tnl tunnel|
         |  ----------  |      |  ----------  |
         |              |      |              |
         |    host1     |      |    host2     |
         '--------------'      '--------------'

    The actual test machinery is implemented in the :any:`BaseEnrtRecipe` class.

    The test wide configuration is implemented in the :any:`BaseTunnelRecipe`
    class.

    The recipe provides additional parameter:

        :param tunnel_mode:
            this parameter specifies the mode of the ip6tnl tunnel, can be any
            of the **any**, **ipip6** or **ip6ip6**
    """

    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    tunnel_mode = ChoiceParam(
        type=StrParam, choices=set(["any", "ipip6", "ip6ip6"]), mandatory=True
    )

    net_ipv6 = IPv6NetworkParam(default="fc00::/64")

    def configure_underlying_network(self, configuration):
        """
        The underlying network for the tunnel consists of the Ethernet
        devices on the matched hosts.
        """
        host1, host2 = self.matched.host1, self.matched.host2
        ipv6_addr = interface_addresses(self.params.net_ipv6)
        for device in [host1.eth0, host2.eth0]:
            device.ip_add(next(ipv6_addr))
            device.up()
            configuration.test_wide_devices.append(device)

        self.wait_tentative_ips(configuration.test_wide_devices)
        configuration.tunnel_endpoints = (host1.eth0, host2.eth0)

    def create_tunnel(self, configuration):
        """
        The ip6tnl tunnel devices are configured with IPv6 addresses.
        """
        endpoint1, endpoint2 = configuration.tunnel_endpoints
        m1 = endpoint1.netns
        m2 = endpoint2.netns
        ip_filter = {"family": AF_INET6}
        endpoint1_ip = endpoint1.ips_filter(**ip_filter)[0]
        endpoint2_ip = endpoint2.ips_filter(**ip_filter)[0]

        a_ip6 = ipaddress("3001:db8:ac10:fe01::2/64")
        b_ip6 = ipaddress("3001:db8:ac10:fe01::3/64")

        m1.ip6tnl = Ip6TnlDevice(
            local=endpoint1_ip,
            remote=endpoint2_ip,
            mode=self.params.tunnel_mode,
            ttl=64,
        )
        m2.ip6tnl = Ip6TnlDevice(
            local=endpoint2_ip,
            remote=endpoint1_ip,
            mode=self.params.tunnel_mode,
            ttl=64,
        )

        # A
        m1.ip6tnl.up()
        m1.ip6tnl.ip_add(a_ip6)

        # B
        m2.ip6tnl.up()
        m2.ip6tnl.ip_add(b_ip6)

        configuration.tunnel_devices.extend([m1.ip6tnl, m2.ip6tnl])
        self.wait_tentative_ips(configuration.tunnel_devices)

    def generate_ping_endpoints(self, config):
        """
        The ping endpoints for this recipe are simply the tunnel endpoints

        Returned as::

            [PingEndpoints(self.matched.host1.ip6tnl, self.matched.host2.ip6tnl)]
        """
        return [PingEndpoints(self.matched.host1.ip6tnl, self.matched.host2.ip6tnl)]

    def get_packet_assert_config(self, ping_config):
        """
        The packet assert test configuration contains filter for ip6 protocol
        and grep patterns to match the ICMP6 echo requests encapsulated
        by Ip6Tnl.
        """
        ip_filter = {"family": AF_INET6, "is_link_local": False}
        m1_carrier = self.matched.host1.eth0
        m2_carrier = self.matched.host2.eth0
        m1_carrier_ip = m1_carrier.ips_filter(**ip_filter)[0]
        m2_carrier_ip = m2_carrier.ips_filter(**ip_filter)[0]

        ip1 = ping_config.client_bind
        ip2 = ping_config.destination_address

        pa_kwargs = {}
        pa_kwargs["p_filter"] = "ip6"

        grep_pattern = [
            "IP6 {} > {}: DSTOPT IP6 {} > {}: ICMP6".format(
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
        return [self.matched.host1.ip6tnl, self.matched.host2.ip6tnl]
