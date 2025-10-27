from collections.abc import Collection
from lnst.Common.IpAddress import (
    AF_INET,
    AF_INET6,
    ipaddress,
    interface_addresses,
)
from lnst.Common.Parameters import IPv4NetworkParam, IPv6NetworkParam
from lnst.Common.Parameters import ChoiceParam, StrParam
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.RecipeCommon.PacketAssert import PacketAssertConf
from lnst.Devices import OvsBridgeDevice, RemoteDevice
from lnst.Recipes.ENRT.helpers import ip_endpoint_pairs
from lnst.Recipes.ENRT.BaseTunnelRecipe import BaseTunnelRecipe
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration
from lnst.Recipes.ENRT.ConfigMixins.PauseFramesHWConfigMixin import (
    PauseFramesHWConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.CoalescingHWConfigMixin import (
    CoalescingHWConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.DevInterruptHWConfigMixin import (
    DevInterruptHWConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.MTUHWConfigMixin import MTUHWConfigMixin
from lnst.Recipes.ENRT.RecipeReqs import SimpleNetworkReq


class GeneveIpsecOvsTunnelRecipe(
    PauseFramesHWConfigMixin,
    CoalescingHWConfigMixin,
    DevInterruptHWConfigMixin,
    MTUHWConfigMixin,
    SimpleNetworkReq,
    BaseTunnelRecipe
):
    """
    This class implements a recipe that configures a Geneve tunnel and IPSec
    using two OpenVSwitch bridges between two hosts. The IPSec configuration is
    handled via the openvswitch-ipsec service automatically and we also
    configure ipsec_skb_mark to ensure that nonencrypted packets don't get
    forwarded.

    The ping test part of the recipe ensures that traffic passes and a packet
    assert evaluation which looks for encrypted packets is used.

    .. code-block:: none

                            .--------.
                 .----------| switch |-------.
                 |          '--------'       |
                 |                           |
         .-------|----------.        .-------|----------.
         | .-----|--------. |        | .-----|--------. |
         | |  .--'-.      | |        | |  .--'-.      | |
         | |  |eth0|      | |        | |  |eth0|      | |
         | |  '----'      | |        | |  '----'      | |
         | |     br-ex OvS| |        | |     br-ex OvS| |
         | |              | |        | |              | |
         | |              | |        | |              | |
         | |              | |        | |              | |
         | .----| |-------. |        | .----| |-------. |
         |     IPSec        |        |     IPSec        |
         | .----| |-------. |        | .----| |-------. |
         | |    | |   OvS | |        | |    | |   OvS | |
         | |    | |       | |        | |    | |       | |
         | | ---' '---    | |        | | ---' '---    | |
         | | gnv tunnel   | |        | | gnv tunnel   | |
         | | ----------   | |        | | ----------   | |
         | '--------------' |        | '--------------' |
         |                  |        |                  |
         |      host1       |        |      host2       |
         '------------------'        '------------------'

    The actual test machinery is implemented in the :any:`BaseEnrtRecipe` class.

    The test wide configuration is implemented in the :any:`BaseTunnelRecipe`
    class.
    """

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

        for host in [host1, host2]:
            host.eth0.up()

            host.br_ex = OvsBridgeDevice()
            host.br_ex.port_add(host.eth0)

            if self.params.carrier_ipversion == "ipv4":
                config.configure_and_track_ip(host.br_ex, next(ipv4_addr))
            else:
                config.configure_and_track_ip(host.br_ex, next(ipv6_addr))

            host.br_ex.up()

        return (host1.br_ex, host2.br_ex)

    def create_tunnel(
        self,
        config: EnrtConfiguration,
        tunnel_endpoints: tuple[RemoteDevice, RemoteDevice],
    ) -> tuple[RemoteDevice, RemoteDevice]:
        """
        OvS bridges are created on each of the matched hosts with two ports.
        One port as an integration port and another port of type Geneve acting
        as a tunnel interface connecting tunneled networks.

        Integration ports are configured with IPv4 and IPv6 addresses
        of the tunneled networks.

        Additionally, the Geneve Tunnel receives a static configuration of
        IPSec options:
        * options:key = 1234
        * options:psk = 'swordfish'

        To test the traffic encryption features.
        """
        endpoint1, endpoint2 = tunnel_endpoints
        m1 = endpoint1.netns
        m2 = endpoint2.netns

        for i, (host, endpoint) in enumerate([(m1, endpoint2), (m2, endpoint1)], 1):
            host.br_in = OvsBridgeDevice()
            host.int0 = host.br_in.port_add(interface_options={"type": "internal"})
            config.configure_and_track_ip(host.int0, ipaddress(f"192.168.200.{i}/24"))
            config.configure_and_track_ip(host.int0, ipaddress(f"fc00:a::{i}/64"))

            local_ip = config.ips_for_device(host.br_ex, (AF_INET if self.params.carrier_ipversion == "ipv4" else AF_INET6))[0]
            remote_ip = config.ips_for_device(endpoint, (AF_INET if self.params.carrier_ipversion == "ipv4" else AF_INET6))[0]
            host.br_in.tunnel_add(
                "geneve",
                {
                    "options:local_ip": local_ip,
                    "options:remote_ip": remote_ip,
                    "options:key": 1234,
                    "options:psk": 'swordfish',
                }
            )

            host.run("ovs-vsctl set Open_vSwitch . other_config:ipsec_skb_mark=0/1")

            host.br_in.up()
            host.int0.up()

        self.wait_tentative_ips(config.configured_devices)

        for host in (self.matched.host1, self.matched.host2):
            host.run("systemctl start openvswitch-ipsec.service")

        return (m1.int0, m2.int0)

    def test_wide_deconfiguration(self, config):
        for host in (self.matched.host1, self.matched.host2):
            host.run("ovs-vsctl remove Open_vSwitch . other_config ipsec_skb_mark")
            host.run("systemctl stop openvswitch-ipsec.service")

        return super().test_wide_deconfiguration(config)

    def generate_ping_endpoints(self, config):
        """
        The ping endpoints for this recipe are simply the tunnel endpoints

        Returned as::

            [PingEndpoints(self.matched.host1.int0, self.matched.host2.int0)]
        """
        return [PingEndpoints(self.matched.host1.int0, self.matched.host2.int0)]

    def generate_perf_endpoints(self, config: EnrtConfiguration) -> list[Collection[EndpointPair[IPEndpoint]]]:
        """
        The perf endpoints for this recipe are simply the two matched NICs:

        host1.eth0 and host2.eth0
        """
        return [ip_endpoint_pairs(config, (self.matched.host1.int0, self.matched.host2.int0))]

    def get_packet_assert_config(self, ping_config):
        """
        The packet assert test configuration contains filter for ip protocol
        and grep patterns to match the ICMP or ICMP6 echo requests.
        """
        if self.params.carrier_ipversion == "ipv4":
            ip_filter = {"family": AF_INET}
        else:
            ip_filter = {"family": AF_INET6, "is_link_local": False}

        m1_carrier = self.matched.host1.br_ex
        m2_carrier = self.matched.host2.br_ex
        m1_carrier_ip = m1_carrier.ips_filter(**ip_filter)[0]
        m2_carrier_ip = m2_carrier.ips_filter(**ip_filter)[0]

        pa_kwargs = {}

        ip_version = "6" if self.params.carrier_ipversion == "ipv6" else ""
        pa_kwargs["p_filter"] = f"ip{ip_version} host {m1_carrier_ip}"
        grep_pattern = f"IP{ip_version} "

        grep_pattern = r"IP{} {} > {}: ESP(.*)".format(
            ip_version, m1_carrier_ip, m2_carrier_ip
        )

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
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
