"""
Module with ForwardingRecipe class that implements ENRT recipe
for testing whole forwarding/routing stack.

Copyright 2025 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
sdobron@redhat.com (Samuel Dobron)
"""

import math
import itertools
from collections.abc import Collection
from socket import AF_INET, AF_INET6
from lnst.Common.Parameters import (
    IPv4NetworkParam,
    IPv6NetworkParam,
    StrParam,
    IntParam,
)
from lnst.Common.IpAddress import interface_addresses
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.Recipes.ENRT.MeasurementGenerators.ForwardingMeasurementGenerator import (
    ForwardingMeasurementGenerator,
)
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration
from lnst.Recipes.ENRT.BaremetalEnrtRecipe import BaremetalEnrtRecipe
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints

from lnst.Common.IpAddress import Ip4Address, Ip6Address
from lnst.Recipes.ENRT.ConfigMixins.MultiDevInterruptHWConfigMixin import (
    MultiDevInterruptHWConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import OffloadSubConfigMixin

from lnst.Controller.NetNamespace import NetNamespace


def filter_ip(config, iface, family):
    return [ip for ip in config._device_ips[iface] if ip.family == family][0]


class ForwardingRecipe(
    MultiDevInterruptHWConfigMixin,
    ForwardingMeasurementGenerator,
    OffloadSubConfigMixin,
    BaremetalEnrtRecipe,
):
    """
    This recipe implements ENRT recipe for testing whole forwarding/routing
    stack. It uses 2 hosts, where host1 is the generator+receiver and host2
    is the forwarder (DUT). Both of them require to have at least 2 NICs,
    traffic is forwarded from host1 via eth0 to host2 and back to host1 via
    eth1.
    Receiver NIC needs to be in separate namespace, so generator (in separate
    namespace) won't deliver it locally but does forward it to forwarder (with
    route defined).

    :attr:`net_ipv4` and :attr:`net_ipv6` are used as a base subnet for
    3 other subnets used in this recipe:
    - egress_net: used for between generator and forwarder
    - ingress_net: used for between forwarder and receiver
    - routed_net: used as a base subnet for "routed/sink networks". First hosts
        of these networks are used as a destination IPs for the flows. Routes
        to these networks are added to generator (via forwarder) and to
        forwader (via receiver). Number of routed networks can be configured
        by :attr:`perf_parallel_processes` parameter as each flow requires
        separate CPU. E.g. for 1 :attr:`perf_parallel_processes` 1 flow
        to 1 network is created, for 2 :attr:`perf_parallel_processes` 2 flows
        to 2 separate newtorks are created, and so on. Multiple networks
        are supposed to simulate multiple networks behind receiver NIC.

    NICs used for this test can be configured by overriding
    :attr:`generator_nic`, :attr:`receiver_nic`, :attr:`forwarder_ingress_nic`
    and :attr:`forwarder_egress_nic` properties and so, this could be used
    as a base for other recipes.


    .. code-block:: none

        +------------host1-----------+             +-------------host2--------+
        |                            |             |                          |
        |                            |             |                          |
        |     +----------------------+egress_net   +------------------------+ |
        |     |  self.generator_nic  +------------>| forwarder_ingress_nic  | |
        |     +----------------------+             +------------------------+ |
        |                            |             |                          |
        |        receiver_ns         |             |                          |
        | +--------------------------+             |                          |
        | |  dest_ips are routed here|             |                          |
        | | +------------------------+ingress_net  +------------------------+ |
        | | |   self.receiver_nic    |<------------+  forwarder_egress_nic  | |
        | | +------------------------+             +------------------------+ |
        | +--------------------------+             |                          |
        +----------------------------+             +--------------------------+
    """

    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))
    host1.eth1 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))
    host2.eth1 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    net_ipv4 = IPv4NetworkParam(default="192.168.241.0/24")
    net_ipv6 = IPv6NetworkParam(default="aa00::/64")

    ratep = IntParam(default=-1)
    burst = IntParam(default=1)

    def test_wide_configuration(self, config: EnrtConfiguration) -> EnrtConfiguration:
        """
        Configures namespaces, networks, IPs and routes.
        """
        host2 = self.matched.host2

        config = super().test_wide_configuration(config)

        self._subnet_test_net(config)

        self.setup_namespaces()

        receiver_ip, receiver_ip6 = self.setup_transit_ips(config)
        config.edge_router_ip = receiver_ip
        config.edge_router_ip6 = receiver_ip6

        host2.run("echo 1 > /proc/sys/net/ipv4/ip_forward")
        host2.run("echo 1 > /proc/sys/net/ipv6/conf/all/forwarding")

        self.wait_tentative_ips(config.configured_devices)

        self.setup_destination_ips(config)

        self.setup_routes(config)

        return config

    def _subnet_test_net(self, config: EnrtConfiguration):
        """
        Subnets larger test network into 3 smaller (transit) networks.
        The names are based on generator point of view.
        """
        config.egress6_net, config.ingress6_net, config.routed6_net, _ = (
            self.params.net_ipv6.subnets(prefixlen_diff=2)
        )
        config.egress4_net, config.ingress4_net, config.routed4_net, _ = (
            self.params.net_ipv4.subnets(prefixlen_diff=2)
        )

    def setup_namespaces(self):
        """
        Setup namespaces.

        This is in separate method, so it can be eventually
        overridden by other recipes.
        """
        host1 = self.matched.host1
        host1.receiver_ns = NetNamespace("lnst-receiver_ns")
        host1.receiver_ns.eth1 = host1.eth1
        host1.receiver_ns.run("ip link set dev lo up")

    def setup_routes(self, config):
        """
        Configures static routes for transit networks.
        """
        generator, forwarder, receiver = (
            self.matched.host1,
            self.matched.host2,
            self.matched.host1.receiver_ns,
        )

        generator.run(
            f"ip route add {config.edge_router_ip} via {filter_ip(config, self.forwarder_ingress_nic, AF_INET)} dev {self.generator_nic.name}"
        )
        generator.run(
            f"ip -6 route add {config.edge_router_ip6} via {filter_ip(config, self.forwarder_ingress_nic, AF_INET6)} dev {self.generator_nic.name}"
        )

        # neighbors needs to be static as receiver is running XDP drop
        # which drops ARP/NDP packets as well
        forwarder.run(
            f"ip neigh add {config.edge_router_ip} lladdr {self.receiver_nic.hwaddr} dev {self.forwarder_egress_nic.name}"
        )
        forwarder.run(
            f"ip -6 neigh add {config.edge_router_ip6} lladdr {self.receiver_nic.hwaddr} dev {self.forwarder_egress_nic.name}"
        )

        # setup default routes in receiver namespace to enable communication TO outside
        receiver.run(
            f"ip route add 0.0.0.0/0 via {filter_ip(config, self.forwarder_egress_nic, AF_INET)} dev {self.receiver_nic.name}"
        )
        receiver.run(
            f"ip -6 route add ::/0 via {filter_ip(config, self.forwarder_egress_nic, AF_INET6)} dev {self.receiver_nic.name}"
        )

    def setup_destination_ips(self, config):
        """
        Configures routed/sink IPs which are used as a destinations.
        Based on :attr:`perf_parallel_processes` parameter, multiple networks
        are created. Each network is used for one flow, so the number of
        networks is equal to the number of flows. Each network is routed
        via forwarder to receiver. The receiver is meant to be edge router
        with multiple networks behind it.

        Routes to these networks needs to be added to both generator and
        forwarder.
        """
        generator, forwarder = self.matched.host1, self.matched.host2
        minimal_prefix_len = max(
            1, math.ceil(math.log2(self.params.perf_parallel_processes))
        )  # how many bites needed for networks
        routed4 = config.routed4_net.subnets(prefixlen_diff=minimal_prefix_len)
        routed6 = config.routed6_net.subnets(prefixlen_diff=minimal_prefix_len)

        config.destination_ips = []  # traffic destination networks
        config.flow_action_ids = []
        for _ in range(self.params.perf_parallel_processes):
            net4 = next(routed4)
            net6 = next(routed6)

            forwarder.run(
                f"ip route add {net4} via {config.edge_router_ip} dev {self.forwarder_egress_nic.name}"
            )
            forwarder.run(
                f"ip -6 route add {net6} via {config.edge_router_ip6} dev {self.forwarder_egress_nic.name}"
            )

            generator.run(
                f"ip route add {net4} via {filter_ip(config, self.forwarder_ingress_nic, AF_INET)} dev {self.generator_nic.name}"
            )
            generator.run(
                f"ip -6 route add {net6} via {filter_ip(config, self.forwarder_ingress_nic, AF_INET6)} dev {self.generator_nic.name}"
            )
            config.destination_ips.append((net4, net6))

    def setup_transit_ips(self, config):
        """
        Configures transit IPs between "routers"
        """
        egress4 = interface_addresses(config.egress4_net)
        ingress4 = interface_addresses(config.ingress4_net)
        egress6 = interface_addresses(config.egress6_net)
        ingress6 = interface_addresses(config.ingress6_net)

        for dev in [self.generator_nic, self.forwarder_ingress_nic]:
            config.configure_and_track_ip(dev, next(egress4))
            config.configure_and_track_ip(dev, next(egress6))
            dev.up_and_wait()

        edge_router_ip = next(ingress4)
        edge_router_ip6 = next(ingress6)
        config.configure_and_track_ip(self.receiver_nic, edge_router_ip)
        config.configure_and_track_ip(self.receiver_nic, edge_router_ip6)
        self.receiver_nic.up_and_wait()

        config.configure_and_track_ip(self.forwarder_egress_nic, next(ingress4))
        config.configure_and_track_ip(self.forwarder_egress_nic, next(ingress6))
        self.forwarder_egress_nic.up_and_wait()

        return edge_router_ip, edge_router_ip6

    def test_wide_deconfiguration(self, config):
        super().test_wide_deconfiguration(config)
        generator, forwarder = self.matched.host1, self.matched.host2

        forwarder.run("echo 0 > /proc/sys/net/ipv4/ip_forward")
        forwarder.run("echo 0 > /proc/sys/net/ipv6/conf/all/forwarding")

        # remove routes and neighs for routed networks:
        for net4, net6 in config.destination_ips:
            # remove routes at forwarder side
            forwarder.run(f"ip route del {net4}")
            forwarder.run(f"ip -6 route del {net6}")

            # remove routes at generator side
            generator.run(f"ip route del {net4}")
            generator.run(f"ip -6 route del {net6}")

        # remove ARP entries
        forwarder.run(
            f"ip neigh del {config.edge_router_ip} dev {self.forwarder_egress_nic.name}"
        )
        forwarder.run(
            f"ip -6 neigh del {config.edge_router_ip6} dev {self.forwarder_egress_nic.name}"
        )

        return config

    def generate_test_wide_description(self, config: EnrtConfiguration):
        """
        Test wide description is extended with the configured addresses
        """
        desc = super().generate_test_wide_description(config)
        desc += [
            "Configured {}.{}.ips = {}".format(dev.host.hostid, dev.name, dev.ips)
            for dev in config.configured_devices
        ]
        return desc

    def generate_ping_endpoints(self, _):
        return [
            PingEndpoints(
                self.generator_nic, self.forwarder_ingress_nic
            ),  # host1 -> host2
            PingEndpoints(
                self.forwarder_egress_nic, self.receiver_nic
            ),  # host2 -> host1
            PingEndpoints(self.generator_nic, self.receiver_nic),
        ]  # host1 -> host1.receiver_ns

    def generate_perf_endpoints(
        self, config: EnrtConfiguration
    ) -> list[Collection[EndpointPair[IPEndpoint]]]:
        """
        Function generates endpoints pairs where flow goes
        from host1.eth0 to host2.eth0. host2 then redirects
        traffic back to host1.eth1.

        Pktgen doesn't do any lookup for MAC based on IP,
        so this function needs to set destination device
        forwarder NIC (because it's MAC is used in PktGen)
        BUT destination IP is set to receiver NIC.

        This is similar to what PC usually do, if it
        receives packet to some other net, it'll set IP
        to the destination and forward it to the next hop,
        which is in this case forwarder (host2).
        """
        endpoint_pairs = []
        dev1 = self.generator_nic
        dev2 = self.receiver_nic

        for ip_type in [Ip4Address, Ip6Address]:
            dev1_ips = [
                ip for ip in config.ips_for_device(dev1) if isinstance(ip, ip_type)
            ]
            dev2_ips = [
                ip[0 if ip_type == Ip4Address else 1][1]
                for ip in config.destination_ips
            ]

            for ip1, ip2 in itertools.product(dev1_ips, dev2_ips):
                endpoint_pairs.append(
                    EndpointPair(
                        IPEndpoint(dev1, ip1),
                        IPEndpoint(dev2, ip2),
                    )
                )

        return [endpoint_pairs]

    @property
    def offload_nics(self):
        """
        Offloading requires physical devices.
        """
        return [
            self.matched.host1.receiver_ns.eth1,
            self.matched.host2.eth0,
            self.matched.host2.eth1,
        ]  # no need to offload generator NIC, there is pktgen running

    @property
    def generator_nic(self):
        return self.matched.host1.eth0

    @property
    def receiver_nic(self):
        return self.matched.host1.receiver_ns.eth1

    @property
    def forwarder_ingress_nic(self):
        return self.matched.host2.eth0

    @property
    def forwarder_egress_nic(self):
        return self.matched.host2.eth1
