import itertools
from collections.abc import Collection
from lnst.Common.IpAddress import (
    AF_INET,
    AF_INET6,
    ipaddress,
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
    IntParam,
    ChoiceParam,
    BoolParam,
    IPv4NetworkParam,
    IPv6NetworkParam,
)
from lnst.Recipes.ENRT.BaseTunnelRecipe import BaseTunnelRecipe
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.RecipeCommon.Perf.Measurements import Flow as PerfFlow
from lnst.Recipes.ENRT.helpers import ip_endpoint_pairs
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin,
)
from lnst.Recipes.ENRT.RecipeReqs import SimpleNetworkReq


class GeneveLwtTunnelRecipe(
    CommonHWSubConfigMixin, OffloadSubConfigMixin, SimpleNetworkReq, BaseTunnelRecipe
):
    """
    This class implements a recipe that configures a simple Geneve lightweight
    tunnel between two hosts.

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

    The recipe provides additional parameters:

        :param carrier_ipversion:
            This parameter specifies whether IPv4 or IPv6 addresses are
            used for the underlying (carrier) network. The value is either
            **ipv4** or **ipv6**

        :param geneve_opts:
            If set to True, the geneve tunnel options will be used in
            encapsulation

        :param flow_count:
            Specified number of flows (encapsulation rules) will be configured
            for the geneve tunnel. Flow is a connection specified by a tunneled
            IPv4/IPv6 address. By default only one flow is configured.
    """

    offload_combinations = Param(
        default=(
            dict(gro="on", gso="on", tso="on"),
            dict(gro="off", gso="on", tso="on"),
            dict(gro="on", gso="off", tso="off"),
            dict(gro="on", gso="on", tso="off"),
        )
    )

    # TODO: ping over IPv6 does not work yet
    ip_versions = Param(default=("ipv4",))
    carrier_ipversion = ChoiceParam(type=StrParam, choices=set(["ipv4", "ipv6"]))
    net_ipv4 = IPv4NetworkParam(default="192.168.101.0/24")
    net_ipv6 = IPv6NetworkParam(default="fc00::/64")
    geneve_opts = BoolParam(default=False)
    flow_count = IntParam(default=1)

    def configure_underlying_network(self, config: EnrtConfiguration) -> tuple[RemoteDevice, RemoteDevice]:
        """
        The underlying network for the tunnel consists of the Ethernet
        devices on the matched hosts.
        """
        host1, host2 = self.matched.host1, self.matched.host2
        tunnel_endpoints = (host1.eth0, host2.eth0)
        ipv4_addr = interface_addresses(self.params.net_ipv4)
        ipv6_addr = interface_addresses(self.params.net_ipv6)
        for device in tunnel_endpoints:
            if self.params.carrier_ipversion == "ipv4":
                config.configure_and_track_ip(device, next(ipv4_addr))
            else:
                config.configure_and_track_ip(device, next(ipv6_addr))
            device.up()

        return tunnel_endpoints

    def create_tunnel(
        self,
        config: EnrtConfiguration,
        tunnel_endpoints: tuple[RemoteDevice, RemoteDevice],
    ) -> tuple[RemoteDevice, RemoteDevice]:
        """
        The Geneve tunnel devices are created with external flag specified
        so that the encapsulation can be defined externally by routes.

        Routes for IPv4 and IPv6 networks to be tunneled through the Geneve are
        added.

        IPv4 and IPv6 addresses of the tunneled networks are configured on
        the loopback devices of the matched hosts.
        """
        endpoint1, endpoint2 = tunnel_endpoints
        m1 = endpoint1.netns
        m2 = endpoint2.netns

        endpoint1_ip = config.ips_for_device(endpoint1)[0]
        endpoint2_ip = config.ips_for_device(endpoint2)[0]

        m1.gnv_tunnel = GeneveDevice(external=True)
        m1.gnv_tunnel.mtu = 1400
        m1.gnv_tunnel.up()

        m2.gnv_tunnel = GeneveDevice(external=True)
        m2.gnv_tunnel.mtu = 1400
        m2.gnv_tunnel.up()
        self._connection_to_tunnelid = {}

        m1_dummy_ips = []
        m1_dummy_ips6 = []
        m2_dummy_ips = []
        m2_dummy_ips6 = []
        for flow_id in range(self.params.flow_count):
            # A
            m1_dummy_ip = ipaddress(f"172.16.10.{flow_id+1}/32")
            m1_dummy_ip6 = ipaddress(f"fc00:a::{flow_id+1}/128")
            m1_dummy_ips.append((m1_dummy_ip, None))
            m1_dummy_ips6.append((m1_dummy_ip6, None))

            # B
            m2_dummy_ip = ipaddress(f"172.16.20.{flow_id+1}/32")
            m2_dummy_ip6 = ipaddress(f"fc00:b::{flow_id+1}/128")
            m2_dummy_ips.append((m2_dummy_ip, None))
            m2_dummy_ips6.append((m2_dummy_ip6, None))

            tunnel_id = flow_id
            port = f"{flow_id:04x}{flow_id:04x}"
            encap = "ip" if self.params.carrier_ipversion == "ipv4" else "ip6"
            geneve_opts = " geneve_opts " + f"0x102:0x80:{port}" if self.params.geneve_opts else ""

            m1.run(
                f"ip route add {m2_dummy_ip} encap {encap} id {tunnel_id} dst {endpoint2_ip}{geneve_opts} dev {m1.gnv_tunnel.name}"
            )
            m2.run(
                f"ip route add {m1_dummy_ip} encap {encap} id {tunnel_id} dst {endpoint1_ip}{geneve_opts} dev {m2.gnv_tunnel.name}"
            )
            m1.run(
                f"ip route add {m2_dummy_ip6} encap {encap} id {tunnel_id} dst {endpoint2_ip}{geneve_opts} dev {m1.gnv_tunnel.name}"
            )
            m2.run(
                f"ip route add {m1_dummy_ip6} encap {encap} id {tunnel_id} dst {endpoint1_ip}{geneve_opts} dev {m2.gnv_tunnel.name}"
            )

            self._connection_to_tunnelid[(str(m1_dummy_ip), str(m2_dummy_ip))] = tunnel_id
            self._connection_to_tunnelid[(str(m1_dummy_ip6), str(m2_dummy_ip6))] = tunnel_id

        config.configure_and_track_ip_bulk(
            [
                (m1.gnv_tunnel, m1_dummy_ips + m1_dummy_ips6),
                (m2.gnv_tunnel, m2_dummy_ips + m2_dummy_ips6),
            ]
        )

        return (m1.gnv_tunnel, m2.gnv_tunnel)

    def generate_ping_endpoints(self, config):
        """
        The ping endpoints for this recipe are the loopback devices that
        are configured with IP addresses of the tunnelled networks.

        Returned as::

            [PingEndpoints(self.matched.host1.lo, self.matched.host2.lo)]
        """
        return [PingEndpoints(self.matched.host1.gnv_tunnel, self.matched.host2.gnv_tunnel)]

    def generate_perf_endpoints(self, config: EnrtConfiguration) -> list[Collection[EndpointPair[IPEndpoint]]]:
        """
        The perf endpoints for this recipe are the loopback devices that
        are configured with IP addresses of the tunnelled networks.
        """
        return [ip_endpoint_pairs(config, (self.matched.host1.gnv_tunnel, self.matched.host2.gnv_tunnel), combination_func=zip)]

    def _create_perf_flows(
        self,
        endpoint_pairs: list[EndpointPair[IPEndpoint]],
        perf_test: str,
        msg_size,
    ) -> list[PerfFlow]:
        """
        This overrides the BaseFlowMeasurementGenerator implementation.

        The base generator expects that parallel flows are generated based on
        the perf_parallel_processes parameter. Individual processes are
        pinned to CPUs selected from perf_tool_cpu list by iterator over the
        perf_parallel_processes parameter.

        The GeneveLwtTunnelRecipe however generates parallel flows based on
        flow_count parameter and creates multiple flow endpoints pairs
        (endpoint_pairs parameter). Since the typical scenario is run with
        perf_parallel_processes=1, we need to move the iterator to outer
        loop, so that individual flows are pinned to separate CPUs in the
        perf_tool_cpu list.
        """
        port_iter = itertools.count(12000)

        flows = []
        i = 0
        for endpoint_pair in endpoint_pairs:
            client, server = endpoint_pair
            for j in range(self.params.perf_parallel_processes):
                server_port = client_port = next(port_iter)
                flows.append(
                    self._create_perf_flow(
                        perf_test,
                        client.device,
                        client.address,
                        client_port if perf_test != "mptcp_stream" else None,
                        server.device,
                        server.address,
                        server_port,
                        msg_size,
                        self.generator_cpupin(i),
                        self.receiver_cpupin(i),
                    )
                )
                i += 1

        return flows

    def get_packet_assert_config(self, ping_config):
        """
        The packet assert test configuration contains filter for ip or ip6
        protocol and grep patterns to match the ICMP or ICMP6 echo requests
        encapsulated by Geneve.
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

        # 14:56:29.576709 IP 192.168.101.1.35551 > 192.168.101.2.6081: Geneve, Flags [none], vni 0x4d2, options [8 bytes]: IP 172.16.10.1 > 172.16.20.1: ICMP echo request, id 64, seq 1, length 64
        options = r", options \[[0-9]+ bytes\]" if self.params.geneve_opts else ""
        tunnel_id = f"{self._connection_to_tunnelid[(str(ip1), str(ip2))]:x}"

        grep_pattern += r"{}\.[0-9]+ > {}\.[0-9]+: Geneve.*vni 0x{}{}: ".format(
            m1_carrier_ip,
            m2_carrier_ip,
            tunnel_id,
            options,
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

    def generate_test_wide_description(self, config: EnrtConfiguration):
        desc = super().generate_test_wide_description(config)
        desc += [
            f"Configured tunnel options = {self.params.geneve_opts}"
        ]
        return desc

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
