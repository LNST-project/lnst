from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Common.IpAddress import (
    AF_INET,
    ipaddress,
    Ip4Address,
    Ip6Address,
)
from lnst.Common.Parameters import Param
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.RecipeCommon.PacketAssert import PacketAssertConf
from lnst.Devices import OvsBridgeDevice
from lnst.Recipes.ENRT.BaseTunnelRecipe import BaseTunnelRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.PauseFramesHWConfigMixin import (
    PauseFramesHWConfigMixin,
)


class GeneveOvsTunnelRecipe(
    PauseFramesHWConfigMixin, OffloadSubConfigMixin, BaseTunnelRecipe
):
    """
    This class implements a recipe that configures a simple Geneve tunnel using
    OpenVSwitch between two hosts.

    .. code-block:: none

                            .--------.
                 .----------| switch |-------.
                 |          '--------'       |
                 |                           |
         .-------|----------.        .-------|----------.
         |    .--'-.        |        |    .--'-.        |
         |    |eth0|        |        |    |eth0|        |
         |    '----'        |        |    '----'        |
         | .----| |-------. |        | .----| |-------. |
         | |    | |   OvS | |        | |    | |   OvS | |
         | |    | |       | |        | |    | |       | |
         | | ---' '---    | |        | | ---' '---    | |
         | | gnv tunnel   | |        | | gnv tunnel   | |
         | | ----------   | |        | | ----------   | |
         | '--------------' |        | '--------------' |
         |                  |        |                  |
         |      host1       |        |       host2      |
         '------------------'        '------------------'

    The actual test machinery is implemented in the :any:`BaseEnrtRecipe` class.

    The test wide configuration is implemented in the :any:`BaseTunnelRecipe`
    class.
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

        self.wait_tentative_ips(configuration.test_wide_devices)
        configuration.tunnel_endpoints = (host1.eth0, host2.eth0)

    def create_tunnel(self, configuration):
        """
        OvS bridges are created on each of the matched hosts with two ports.
        One port as an integration port and another port of type Geneve acting
        as a tunnel interface connecting tunneled networks.

        Integration ports are configured with IPv4 and IPv6 addresses
        of the tunneled networks.
        """
        endpoint1, endpoint2 = configuration.tunnel_endpoints
        m1 = endpoint1.netns
        m2 = endpoint2.netns
        ip_filter = {"family": AF_INET}

        for i, (host, endpoint) in enumerate([(m1, endpoint2), (m2, endpoint1)]):
            remote_ip = endpoint.ips_filter(**ip_filter)[0]
            host.br0 = OvsBridgeDevice()
            host.int0 = host.br0.port_add(interface_options={"type": "internal"})
            configuration.tunnel_devices.append(host.int0)
            host.int0.ip_add(ipaddress("192.168.200." + str(i + 1) + "/24"))
            host.int0.ip_add(ipaddress("fc00::" + str(i + 1) + "/64"))

            host.br0.tunnel_add(
                "geneve", {"options:remote_ip": remote_ip, "options:key": 1234}
            )

            host.br0.up()
            host.int0.up()

        self.wait_tentative_ips(configuration.tunnel_devices)

    def generate_ping_endpoints(self, config):
        """
        The ping endpoints for this recipe are simply the tunnel endpoints

        Returned as::

            [PingEndpoints(self.matched.host1.int0, self.matched.host2.int0)]
        """
        return [PingEndpoints(self.matched.host1.int0, self.matched.host2.int0)]

    def get_packet_assert_config(self, ping_config):
        """
        The packet assert test configuration contains filter for ip protocol
        and grep patterns to match the ICMP or ICMP6 echo requests.
        """
        ip_filter = {"family": AF_INET}
        m1_carrier = self.matched.host1.eth0
        m2_carrier = self.matched.host2.eth0
        m1_carrier_ip = m1_carrier.ips_filter(**ip_filter)[0]
        m2_carrier_ip = m2_carrier.ips_filter(**ip_filter)[0]

        ip1 = ping_config.client_bind
        ip2 = ping_config.destination_address

        pa_kwargs = {}
        pa_kwargs["p_filter"] = "ip"

        grep_pattern = "IP {}\.[0-9]+ > {}\.[0-9]+: Geneve.*vni 0x4d2: ".format(
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
