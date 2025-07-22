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
from lnst.Common.LnstError import LnstError
from lnst.Common.Parameters import (
    Param,
    ChoiceParam,
    StrParam,
    IntParam,
    BoolParam,
    IPv4NetworkParam,
    IPv6NetworkParam,
)
from lnst.Controller.NetNamespace import NetNamespace
from lnst.RecipeCommon.Ping.Recipe import PingConf
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.RecipeCommon.PacketAssert import PacketAssertConf
from lnst.Devices import OvsBridgeDevice, RemoteDevice, VethPair
from lnst.Recipes.ENRT.BaseTunnelRecipe import BaseTunnelRecipe
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.RecipeCommon.Perf.Measurements import Flow as PerfFlow
from lnst.Recipes.ENRT.helpers import ip_endpoint_pairs

from lnst.Recipes.ENRT.ConfigMixins.CoalescingHWConfigMixin import (
    CoalescingHWConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.MultiDevInterruptHWConfigMixin import (
    MultiDevInterruptHWConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.DevRxHashFunctionConfigMixin import (
    DevRxHashFunctionConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.DevNfcRxFlowHashConfigMixin import (
    DevNfcRxFlowHashConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.DevQueuesConfigMixin import (
    DevQueuesConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.MTUHWConfigMixin import MTUHWConfigMixin
from lnst.Recipes.ENRT.ConfigMixins.PauseFramesHWConfigMixin import (
    PauseFramesHWConfigMixin,
)

from lnst.Recipes.ENRT.RecipeReqs import SimpleNetworkReq


class GeneveOvsNetnsTunnelRecipe(
    DevRxHashFunctionConfigMixin,
    DevNfcRxFlowHashConfigMixin,
    DevQueuesConfigMixin,
    PauseFramesHWConfigMixin,
    CoalescingHWConfigMixin,
    MultiDevInterruptHWConfigMixin,
    MTUHWConfigMixin,
    OffloadSubConfigMixin,
    SimpleNetworkReq,
    BaseTunnelRecipe
):
    """
    This class implements a recipe that configures Geneve tunnel(s) connecting
    network namespaces between two hosts using OpenVSwitch.

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
         | '-.----------.-' |        | '-.----------.-' |
         |   |          |   |        |   |          |   |
         |.--'--.    .--'--.|        |.--'--.    .--'--.|
         || ns1 | .. | nsX ||        || ns1 | .. | nsX ||
         |'-----'    '-----'|        |'-----'    '-----'|
         |                  |        |                  |
         |      host1       |        |       host2      |
         '------------------'        '------------------'

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
        ipv4_addr = interface_addresses(self.params.net_ipv4)
        ipv6_addr = interface_addresses(self.params.net_ipv6)
        for device in [host1.eth0, host2.eth0]:
            device.up()
            if self.params.carrier_ipversion == "ipv4":
                config.configure_and_track_ip(device, next(ipv4_addr))
            else:
                config.configure_and_track_ip(device, next(ipv6_addr))

        return (host1.eth0, host2.eth0)

    def create_tunnel(
        self,
        config: EnrtConfiguration,
        tunnel_endpoints: tuple[RemoteDevice, RemoteDevice],
    ) -> tuple[RemoteDevice, RemoteDevice]:
        """
        Based on flow_count parameter each Geneve tunnel is created in
        following way.

        OvS bridges are created on each of the matched hosts. A Geneve tunnel
        is added to each bridge with remote_ip parameter and tunnel id defined
        by openflow rule. A TLV mapping is added to add tunnel options in the
        Geneve packets through openflow rule.

        A veth pair is created on both machines, one device is added to the
        OvS bridge, the other moved to separate network namespace.
        The device in the network namespace is assigned IPv4 and IPv6
        address that will be tunneled over Geneve tunnel.

        For each Geneve tunnel, an openflow rule is created so that tunnel id
        and tunnel options are set based on the iterator value over flow_count
        parameter.
        """
        endpoint1, endpoint2 = tunnel_endpoints
        m1 = endpoint1.netns
        m2 = endpoint2.netns

        for host, endpoint in [(m1, endpoint2), (m2, endpoint1)]:
            host.br0 = OvsBridgeDevice()
            remote_ip = config.ips_for_device(endpoint, (AF_INET if self.params.carrier_ipversion == "ipv4" else AF_INET6))[0]
            host.br0.tunnel_add(
                "geneve", {"options:remote_ip": remote_ip, "options:key": "flow"}
            )
            host.br0.up()
            host.run(f"ovs-ofctl add-tlv-map {host.br0.name} " + "\"{class=0x0102,type=0x80,len=8}->tun_metadata0\"")

        device_ipv4_addresses = []
        device_ipv6_addresses = []
        config.tunneled_endpoints = []
        for flow_id in range(self.params.flow_count):
            m1_dummy_ip = ipaddress(f"172.16.10.{flow_id+1}/32")
            m1_dummy_ip6 = ipaddress(f"fc00:a::{flow_id+1}/128")
            m2_dummy_ip = ipaddress(f"172.16.20.{flow_id+1}/32")
            m2_dummy_ip6 = ipaddress(f"fc00:b::{flow_id+1}/128")

            # first host
            setattr(m1, f"netns{flow_id}", NetNamespace(f"subnet{flow_id}"))
            m1_netns = getattr(m1, f"netns{flow_id}")

            m1_veth, m1_veth_peer = VethPair()
            # store the devices under custom names that includes the tunnel id
            setattr(m1, f"veth{flow_id}", m1_veth)
            setattr(m1, f"veth_peer{flow_id}", m1_veth_peer)

            m1.br0.port_add(m1_veth)

            m1_netns.veth_peer = m1_veth_peer
            m1_veth.up()
            m1_netns.veth_peer.up()

            device_ipv4_addresses.append((m1_netns.veth_peer, [(m1_dummy_ip, None)]))
            device_ipv6_addresses.append((m1_netns.veth_peer, [(m1_dummy_ip6, None)]))

            # second host
            setattr(m2, f"netns{flow_id}", NetNamespace(f"subnet{flow_id}"))
            m2_netns = getattr(m2, f"netns{flow_id}")

            m2_veth, m2_veth_peer = VethPair()
            # store the devices under custom names that includes tunnel id
            setattr(m2, f"veth{flow_id}", m2_veth)
            setattr(m2, f"veth_peer{flow_id}", m2_veth_peer)

            m2.br0.port_add(m2_veth)

            m2_netns.veth_peer = m2_veth_peer
            m2_veth.up()
            m2_netns.veth_peer.up()

            device_ipv4_addresses.append((m2_netns.veth_peer, [(m2_dummy_ip, None)]))
            device_ipv6_addresses.append((m2_netns.veth_peer, [(m2_dummy_ip6,None)]))

            config.tunneled_endpoints.append((m1_netns.veth_peer, m2_netns.veth_peer))

        config.configure_and_track_ip_bulk(device_ipv4_addresses + device_ipv6_addresses)

        self._connection_to_tunnelid = {}

        for flow_id in range(self.params.flow_count):
            port = f"0x{flow_id:04x}{flow_id:04x}"

            m1_dummy_ip = device_ipv4_addresses[flow_id*2][1][0][0]
            m1_dummy_ip6 = device_ipv6_addresses[flow_id*2][1][0][0]
            m2_dummy_ip = device_ipv4_addresses[flow_id*2 + 1][1][0][0]
            m2_dummy_ip6 = device_ipv6_addresses[flow_id*2 + 1][1][0][0]

            m1.br0.flow_add(
                f"ip,ip_src={m1_dummy_ip}/{m1_dummy_ip.prefixlen},actions=set_tunnel:{flow_id}" + (f",set_field:{port}->tun_metadata0" if self.params.geneve_opts else "") + ",normal"
            )
            m1.br0.flow_add(
                f"ipv6,ipv6_src={m1_dummy_ip6}/{m1_dummy_ip6.prefixlen},actions=set_tunnel:{flow_id}" + (f",set_field:{port}->tun_metadata0" if self.params.geneve_opts else "") + ",normal"
            )

            # TODO: created namespace does not have even the default route
            # defined, not sure if this is expected, but let's add explicit
            # route to the other endpoint
            m1_netns = getattr(m1, f"netns{flow_id}")
            m1_netns.run(f"ip route add {m2_dummy_ip}/{m2_dummy_ip.prefixlen} dev {m1_netns.veth_peer.name}")
            m1_netns.run(f"ip route add {m2_dummy_ip6}/{m2_dummy_ip6.prefixlen} dev {m1_netns.veth_peer.name}")

            m2.br0.flow_add(
                f"ip,ip_src={m2_dummy_ip}/{m2_dummy_ip.prefixlen},actions=set_tunnel:{flow_id}" + (f",set_field:{port}->tun_metadata0" if self.params.geneve_opts else "") + ",normal"
            )
            m2.br0.flow_add(
                f"ipv6,ipv6_src={m2_dummy_ip6}/{m2_dummy_ip6.prefixlen},actions=set_tunnel:{flow_id}" + (f",set_field:{port}->tun_metadata0" if self.params.geneve_opts else "") + ",normal"
            )

            m2_netns = getattr(m2, f"netns{flow_id}")
            m2_netns.run(f"ip route add {m1_dummy_ip}/{m1_dummy_ip.prefixlen} dev {m2_netns.veth_peer.name}")
            m2_netns.run(f"ip route add {m1_dummy_ip6}/{m1_dummy_ip6.prefixlen} dev {m2_netns.veth_peer.name}")

            m1.run(f"ovs-ofctl dump-flows {m1.br0.name}")
            m2.run(f"ovs-ofctl dump-flows {m2.br0.name}")

            self._connection_to_tunnelid[(str(m1_dummy_ip), str(m2_dummy_ip))] = flow_id
            self._connection_to_tunnelid[(str(m1_dummy_ip6), str(m2_dummy_ip6))] = flow_id

        # TODO: not sure what to return here, but since this is used only in
        # BaseTunnelRecipe.generate_test_wide_description, go with empty
        return []

    def generate_ping_configurations(self, config):
        """Overridden ping test configuration generator

        The generator loops over all endpoint pairs to test ping between
        (generated by the :any:`generate_ping_endpoints` method) then over all
        the selected :any:`ip_versions` and finally over all the IP addresses
        that fit those criteria.

        If we want to run ping between all endpoint pairs in parallel
        (self.params.ping_parallel=True) we need to group all the veth_peer
        endpoints into single list.

        :return: list of Ping configurations to test in parallel
        :rtype: List[:any:`PingConf`]
        """
        for ipv in self.params.ip_versions:
            endpoint_groups = []
            if self.params.ping_parallel:
                """
                [ [(ep1, ep2), (ep3, ep4)] ]

                """
                endpoint_groups = [
                    [
                        endpoints
                        for endpoints
                        in self.generate_ping_endpoints(config)
                    ]
                ]
            else:
                """
                [ [(ep1, ep2)], [(ep3, ep4)] ]
                """
                endpoint_groups = [
                    [endpoints]
                    for endpoints
                    in self.generate_ping_endpoints(config)
                ]

            for endpoint_group in endpoint_groups:
                ping_conf_list = []
                for endpoints in endpoint_group:
                    if ipv == "ipv6" and not endpoints.reachable:
                        continue

                    ip_filter = {}
                    if ipv == "ipv4":
                        ip_filter.update(family = AF_INET)
                    elif ipv == "ipv6":
                        ip_filter.update(family = AF_INET6)
                        ip_filter.update(is_link_local = False)

                    endpoint1, endpoint2 = endpoints.endpoints
                    endpoint1_ips = endpoint1.ips_filter(**ip_filter)
                    endpoint2_ips = endpoint2.ips_filter(**ip_filter)

                    if len(endpoint1_ips) != len(endpoint2_ips):
                        raise LnstError("Source/destination ip lists are of different size.")

                    for src_addr, dst_addr in zip(endpoint1_ips, endpoint2_ips):
                        pconf = PingConf(client = endpoint1.netns,
                                         client_bind = src_addr,
                                         destination = endpoint2.netns,
                                         destination_address = dst_addr,
                                         count = self.params.ping_count,
                                         interval = self.params.ping_interval,
                                         size = self.params.ping_psize,
                                         )

                        ping_evaluators = self.generate_ping_evaluators(
                                pconf, endpoints)

                        pconf.register_evaluators(ping_evaluators)
                        ping_conf_list.append(pconf)

                        if self.params.ping_bidirect:
                            ping_conf_list.append(self._create_reverse_ping(pconf))

                if ping_conf_list:
                    yield ping_conf_list

    def generate_ping_endpoints(self, config):
        """
        The ping endpoints for this recipe are the IP/IPv6 addresses configured
        on the veth_peer devices in the network namespaces
        """
        return [
            PingEndpoints(first, second)
            for first, second in config.tunneled_endpoints
        ]

    def generate_perf_endpoints(self, config: EnrtConfiguration) -> list[Collection[EndpointPair[IPEndpoint]]]:
        """
        The perf endpoints for this recipe are the devices in individual network
        namespaces that are configured with IP addresses of the tunnelled networks.
        """
        return [
            ip_endpoint_pairs(
                config,
                *(
                    (first, second)
                    for (first, second) in config.tunneled_endpoints
                ),
                combination_func=zip
            )
        ]

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

        pa_config = PacketAssertConf(self.matched.host2, m2_carrier, **pa_kwargs)

        return pa_config

    def generate_test_wide_description(self, config: EnrtConfiguration):
        desc = super().generate_test_wide_description(config)
        desc += [
            f"Configured tunnel options = {self.params.geneve_opts}"
        ]
        return desc

    def test_wide_deconfiguration(self, config):
        del config.tunneled_endpoints

        return super().test_wide_deconfiguration(config)

    def _create_perf_flows(
        self,
        endpoint_pairs: list[EndpointPair[IPEndpoint]],
        perf_test: str,
        msg_size,
    ) -> list[PerfFlow]:
        """
        This overrides the BaseFlowMeasurementGenerator implementation.

        The generator pins iperf processes to the CPUs defined in perf_tool_cpu
        list based on the perf_parallel_processes. The GeneveLwtTunnelRecipe
        however needs to pin the CPUs based on the flow_count (tunnel flow is
        defined by the perf endpoints), otherwise each each of the tunnel flows
        would be pinned to the first CPU in the perf_tool_cpu list.
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

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def offload_nics(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def pause_frames_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
