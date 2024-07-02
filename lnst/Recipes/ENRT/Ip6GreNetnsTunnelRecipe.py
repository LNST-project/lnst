from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Controller.NetNamespace import NetNamespace
from lnst.Common.IpAddress import (
    AF_INET6,
    Ip4Address,
    Ip6Address,
    interface_addresses,
)
from lnst.Common.Parameters import (
    Param,
    IPv6NetworkParam,
)
from lnst.Devices import Ip6GreDevice, VethPair, BridgeDevice, RemoteDevice
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.RecipeCommon.PacketAssert import PacketAssertConf
from lnst.Recipes.ENRT.BaseTunnelRecipe import BaseTunnelRecipe
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration
from lnst.Recipes.ENRT.ConfigMixins.MTUHWConfigMixin import (
    MTUHWConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.PauseFramesHWConfigMixin import (
    PauseFramesHWConfigMixin,
)


class Ip6GreNetnsTunnelRecipe(
    MTUHWConfigMixin, PauseFramesHWConfigMixin, OffloadSubConfigMixin, BaseTunnelRecipe
):
    r"""
    This class implements a recipe that configures a IP6GRE tunnel between
    two network namespaces on two hosts.

    .. code-block:: none

                              .--------.
                 .------------| switch |--------.
                 |            '--------'        |
                 |                              |
         .-------|------------.         .-------|------------.
         |    .--'---.        |         |    .--'---.        |
         |    | eth0 |        |         |    | eth0 |        |
         |    '------'        |         |    '------'        |
         |       \            |         |       \            |
         |        .--------.  |         |        .--------.  |
         |        | bridge |  |         |        | bridge |  |
         |        '--------'  |         |        '--------'  |
         |       /            |         |       /            |
         |   .-------.        |         |   .-------.        |
         |   | veth0 |        |         |   | veth0 |        |
         |   '--.----'        |         |   '--.----'        |
         |  .----\---------.  |         |  .----\---------.  |
         |  |     \  netns |  |         |  |     \  netns |  |
         |  |  .---\---.   |  |         |  |  .---\---.   |  |
         |  |  |veth0_1|   |  |         |  |  |veth0_1|   |  |
         |  |  '-------'   |  |         |  |  '-------'   |  |
         |  |      | |     |  |         |  |      | |     |  |
         |  |  ----' '---- |  |         |  |  ----' '---- |  |
         |  |  gre6 tunnel |  |         |  |  gre6 tunnel |  |
         |  |  ----------- |  |         |  |  ----------- |  |
         |  '--------------'  |         |  '--------------'  |
         |                    |         |                    |
         |        host1       |         |        host1       |
         '--------------------'         '--------------------'

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

    net_ipv6 = IPv6NetworkParam(default="fc00::/64")

    def configure_underlying_network(self, config: EnrtConfiguration) -> tuple[RemoteDevice, RemoteDevice]:
        """
        The underlying network for the tunnel consists of

        - an Ethernet device on each of the matched hosts
        - a pair of veth devices on each host with one end of the pair
          connected to Ethernet device through bridge and the second one
          moved to a network namespace

        The veth devices in the namespaces are assigned an IPv6 address and
        will be used as tunnel endpoints
        """
        host1, host2 = self.matched.host1, self.matched.host2

        host1.newns = NetNamespace("host1-net1")
        host2.newns = NetNamespace("host2-net1")

        # veth_pair
        host1.veth0, host1.veth1 = VethPair()
        host2.veth0, host2.veth1 = VethPair()

        # one veth end to netns
        host1.newns.veth1 = host1.veth1
        host2.newns.veth1 = host2.veth1

        # second veth bridged with NIC
        host1.bridge = BridgeDevice()
        host1.bridge.slave_add(host1.veth0)
        host1.bridge.slave_add(host1.eth0)
        host2.bridge = BridgeDevice()
        host2.bridge.slave_add(host2.veth0)
        host2.bridge.slave_add(host2.eth0)


        for device in [
            host1.veth0,
            host2.veth0,
            host1.bridge,
            host2.bridge,
            host1.eth0,
            host2.eth0,
        ]:
            device.up()
            config.track_device(device)

        ipv6_addr = interface_addresses(self.params.net_ipv6)
        for device in [host1.newns.veth1, host2.newns.veth1]:
            config.configure_and_track_ip(device, next(ipv6_addr))
            device.up()

        host1.veth0.up()
        host2.veth0.up()

        return (host1.newns.veth1, host2.newns.veth1)

    def create_tunnel(
        self,
        config: EnrtConfiguration,
        tunnel_endpoints: tuple[RemoteDevice, RemoteDevice],
    ) -> tuple[RemoteDevice, RemoteDevice]:
        """
        The GRE tunnel devices are created in the network namespaces and
        configured with local and remote ip addresses matching the veth
        devices IP addresses.

        The IP6GRE tunnel devices are configured with IPv4 and IPv6 addresses
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

        m1.gre6_tunnel = Ip6GreDevice(local=endpoint1_ip, remote=endpoint2_ip)
        m2.gre6_tunnel = Ip6GreDevice(local=endpoint2_ip, remote=endpoint1_ip)

        # A
        m1.gre6_tunnel.up()
        config.configure_and_track_ip(m1.gre6_tunnel, a_ip4)
        config.configure_and_track_ip(m1.gre6_tunnel, a_ip6)
        m1.run("ip -4 route add {} dev {}".format(b_net4, m1.gre6_tunnel.name))
        m1.run("ip -6 route add {} dev {}".format(b_net6, m1.gre6_tunnel.name))

        # B
        m2.gre6_tunnel.up()
        config.configure_and_track_ip(m2.gre6_tunnel, b_ip4)
        config.configure_and_track_ip(m2.gre6_tunnel, b_ip6)
        m2.run("ip -4 route add {} dev {}".format(a_net4, m2.gre6_tunnel.name))
        m2.run("ip -6 route add {} dev {}".format(a_net6, m2.gre6_tunnel.name))

        return (m1.gre6_tunnel, m2.gre6_tunnel)

    def generate_ping_endpoints(self, config):
        """
        The ping endpoints for this recipe are simply the tunnel endpoints

        Returned as::

            [PingEndpoints(self.matched.host1.newns.gre6_tunnel, self.matched.host2.newns.gre6_tunnel)]
        """
        return [
            PingEndpoints(
                self.matched.host1.newns.gre6_tunnel,
                self.matched.host2.newns.gre6_tunnel,
            )
        ]

    def get_packet_assert_config(self, ping_config):
        """
        The packet assert test configuration contains filter for ip6 protocol
        and grep patterns to match the ICMP or ICMP6 echo requests encapsulated
        by GRE.
        """
        ip_filter = {"family": AF_INET6, "is_link_local": False}
        m1_carrier = self.matched.host1.newns.veth1
        m2_carrier = self.matched.host2.newns.veth1
        m1_carrier_ip = m1_carrier.ips_filter(**ip_filter)[0]
        m2_carrier_ip = m2_carrier.ips_filter(**ip_filter)[0]

        ip1 = ping_config.client_bind
        ip2 = ping_config.destination_address

        pa_kwargs = {}
        pa_kwargs["p_filter"] = "ip6"

        if isinstance(ip2, Ip4Address):
            pat1 = r"{} > {}:( DSTOPT)? GREv0, .* IP {} > {}: ICMP echo request".format(
                m1_carrier_ip, m2_carrier_ip, ip1, ip2
            )
            pat2 = r"{} > {}:( DSTOPT)? GREv0 \| {} > {}: ICMP echo request".format(
                m1_carrier_ip, m2_carrier_ip, ip1, ip2
            )
            grep_pattern = [r"({})|({})".format(pat1, pat2)]
        elif isinstance(ip2, Ip6Address):
            pat1 = (
                r"{} > {}:( DSTOPT)? GREv0, .* IP6 {} > {}: ICMP6, echo request".format(
                    m1_carrier_ip, m2_carrier_ip, ip1, ip2
                )
            )
            pat2 = r"{} > {}:( DSTOPT)? GREv0 \| {} > {}: ICMP6, echo request".format(
                m1_carrier_ip, m2_carrier_ip, ip1, ip2
            )
            grep_pattern = [r"({})|({})".format(pat1, pat2)]
        else:
            raise Exception("The destination address is nor IPv4 or IPv6 address")

        pa_kwargs["grep_for"] = grep_pattern

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
        host1, host2 = self.matched.host1, self.matched.host2

        return [host1.newns.gre6_tunnel, host2.newns.gre6_tunnel]
