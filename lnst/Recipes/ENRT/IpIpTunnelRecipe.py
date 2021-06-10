from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Common.IpAddress import (
    AF_INET,
    ipaddress,
)
from lnst.Devices import IpIpDevice
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.RecipeCommon.PacketAssert import PacketAssertConf
from lnst.Common.Parameters import StrParam, ChoiceParam
from lnst.Recipes.ENRT.BaseTunnelRecipe import BaseTunnelRecipe
from lnst.Recipes.ENRT.ConfigMixins.MTUHWConfigMixin import MTUHWConfigMixin
from lnst.Recipes.ENRT.ConfigMixins.PauseFramesHWConfigMixin import (
    PauseFramesHWConfigMixin,
)


class IpIpTunnelRecipe(MTUHWConfigMixin, PauseFramesHWConfigMixin, BaseTunnelRecipe):
    """
    This class implements a recipe that configures a simple IpIp tunnel between
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
         |  ipip tunnel |      |  ipip tunnel |
         |  ----------  |      |  ----------  |
         |              |      |              |
         |    host1     |      |    host2     |
         '--------------'      '--------------'

    The actual test machinery is implemented in the :any:`BaseEnrtRecipe` class.

    The test wide configuration is implemented in the :any:`BaseTunnelRecipe`
    class.

    The recipe provides additional parameter:

        :param tunnel_mode:
            this parameter specifies the mode of the IPIP tunnel, can be any
            of the **any**, **ipip** or **mplsip**
    """

    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    tunnel_mode = ChoiceParam(
        type=StrParam, choices=set(["any", "ipip", "mplsip"]), mandatory=True
    )

    def configure_underlying_network(self, configuration):
        """
        The underlying network for the tunnel consists of the Ethernet
        devices on the matched hosts.
        """
        host1, host2 = self.matched.host1, self.matched.host2
        for i, device in enumerate([host1.eth0, host2.eth0]):
            device.ip_add(ipaddress("172.16.200." + str(i + 1) + "/16"))
            device.up()
            configuration.test_wide_devices.append(device)

        configuration.tunnel_endpoints = (host1.eth0, host2.eth0)

    def create_tunnel(self, configuration):
        """
        The ipip tunnel devices are configured with IPv4 addresses.
        """
        endpoint1, endpoint2 = configuration.tunnel_endpoints
        m1 = endpoint1.netns
        m2 = endpoint2.netns
        ip_filter = {"family": AF_INET}
        endpoint1_ip = endpoint1.ips_filter(**ip_filter)[0]
        endpoint2_ip = endpoint2.ips_filter(**ip_filter)[0]

        a_ip4 = ipaddress("192.168.200.1/24")
        b_ip4 = ipaddress("192.168.200.2/24")

        m1.ipip_tunnel = IpIpDevice(
            local=endpoint1_ip,
            remote=endpoint2_ip,
            mode=self.params.tunnel_mode,
            ttl=64,
        )
        m2.ipip_tunnel = IpIpDevice(
            local=endpoint2_ip,
            remote=endpoint1_ip,
            mode=self.params.tunnel_mode,
            ttl=64,
        )

        # A
        m1.ipip_tunnel.up()
        m1.ipip_tunnel.ip_add(a_ip4)

        # B
        m2.ipip_tunnel.up()
        m2.ipip_tunnel.ip_add(b_ip4)

        configuration.tunnel_devices.extend([m1.ipip_tunnel, m2.ipip_tunnel])

    def generate_ping_endpoints(self, config):
        """
        The ping endpoints for this recipe are simply the tunnel endpoints

        Returned as::

            [PingEndpoints(self.matched.host1.ipip_tunnel, self.matched.host2.ipip_tunnel)]
        """
        return [
            PingEndpoints(
                self.matched.host1.ipip_tunnel, self.matched.host2.ipip_tunnel
            )
        ]

    def get_packet_assert_config(self, ping_config):
        """
        The packet assert test configuration contains filter for ip protocol
        and grep patterns to match the ICMP echo requests encapsulated
        by IPIP.
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
        grep_pattern = [
            "IP {} > {}: IP {} > {}: ICMP".format(
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
        return [self.matched.host1.ipip_tunnel, self.matched.host2.ipip_tunnel]
