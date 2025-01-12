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

from lnst.Common.Parameters import (
    IntParam,
)
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT import SimpleNetnsRouterRecipe
from lnst.Recipes.ENRT.MeasurementGenerators.ForwardingMeasurementGenerator import (
    ForwardingMeasurementGenerator,
)
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints

from lnst.Recipes.ENRT.ConfigMixins.MultiDevInterruptHWConfigMixin import (
    MultiDevInterruptHWConfigMixin,
)

from lnst.Controller.NetNamespace import NetNamespace
from lnst.Recipes.ENRT.PerfTestMixins.DevFlowsPinningMixin import DevFlowsPinningMixin

from .SimpleNetnsRouterRecipe import SimpleNetnsRouterRecipe


class ForwardingRecipe(
    DevFlowsPinningMixin,
    MultiDevInterruptHWConfigMixin,
    ForwardingMeasurementGenerator,
    SimpleNetnsRouterRecipe,
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

    NICs used for this test can be configured by overriding
    :attr:`generator_nic`, :attr:`receiver_nic`, :attr:`forwarder_ingress_nic`
    and :attr:`forwarder_egress_nic` properties and so, this could be used
    as a base for other recipes requiring purely baremetal forwarding setup.


    .. code-block:: none

        +------------host1-----------+              +-----------host2----------+
        |                            |              |                          |
        |     +----------------------+net_ipv{4,6}  +------------------------+ |
        |     |  self.generator_nic  +------------->| forwarder_ingress_nic  | |
        |     +----------------------+              +------------------------+ |
        |                            |              |                          |
        |        receiver_ns         |              |                          |
        | +--------------------------+              |                          |
        | | +------------------------+netns_ipv{4,6}+------------------------+ |
        | | |   self.receiver_nic    |<-------------+  forwarder_egress_nic  | |
        | | +------------------------+              +------------------------+ |
        | +--------------------------+              |                          |
        +----------------------------+              +--------------------------+
    """

    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))
    host1.eth1 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))
    host2.eth1 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    ratep = IntParam(default=-1)
    burst = IntParam(default=1)

    def test_wide_configuration(self, config: EnrtConfiguration) -> EnrtConfiguration:
        """
        Configures namespaces, networks, IPs and routes.
        """
        config = super().test_wide_configuration(config)

        self.wait_tentative_ips(config.configured_devices)

        # neighbors needs to be static as receiver is running XDP drop
        # which drops ARP/NDP packets as well
        forwarder = self.matched.host2
        forwarder.run(
            f"ip neigh add {self.params.netns_ipv4[2]} lladdr {self.receiver_nic.hwaddr} dev {self.forwarder_egress_nic.name}"
        )
        forwarder.run(
            f"ip -6 neigh add {self.params.netns_ipv6[2]} lladdr {self.receiver_nic.hwaddr} dev {self.forwarder_egress_nic.name}"
        )

        return config

    def setup_namespaces(self):
        """
        Setup namespaces.

        This is in separate method, so it can be eventually
        overridden by other recipes.
        """
        host1 = self.matched.host1
        host1.ns = NetNamespace("lnst-receiver_ns")
        host1.ns.eth1 = host1.eth1
        host1.ns.run("ip link set dev lo up")

    def test_wide_deconfiguration(self, config):
        super().test_wide_deconfiguration(config)
        # remove static ARP entries
        self.matched.host2.run(
            f"ip neigh del {self.params.netns_ipv4[2]} dev {self.forwarder_egress_nic.name}"
        )
        self.matched.host2.run(
            f"ip -6 neigh del {self.params.netns_ipv6[2]} dev {self.forwarder_egress_nic.name}"
        )

        return config

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

    @property
    def offload_nics(self):
        """
        Offloading requires physical devices.
        """
        return [
            self.matched.host1.ns.eth1,
            self.matched.host2.eth0,
            self.matched.host2.eth1,
        ]  # no need to offload generator NIC, there is pktgen running

    @property
    def receiver_nic(self):
        return self.matched.host1.ns.eth1

    @property
    def forwarder_ingress_nic(self):
        return self.matched.host2.eth0

    @property
    def forwarder_egress_nic(self):
        return self.matched.host2.eth1

    def steer_flow_to(self, _):
        return [self.forwarder_ingress_nic]
