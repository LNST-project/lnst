"""
Module with generator class for Forwarding Recipe.

Copyright 2025 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
sdobron@redhat.com (Samuel Dobron)
"""

import itertools

from lnst.Recipes.ENRT.MeasurementGenerators.BaseFlowMeasurementGenerator import (
    BaseFlowMeasurementGenerator,
)
from lnst.RecipeCommon.Perf.Measurements.ForwardingMeasurement import (
    ForwardingMeasurement,
)
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import (
        BaseFlowMeasurement
)


from lnst.RecipeCommon.Perf.Measurements import Flow as PerfFlow
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint


class ForwardingMeasurementGenerator(BaseFlowMeasurementGenerator):
    @property
    def net_perf_tool_class(self):
        def ForwardingMeasurement_partial(*args, **kwargs):
            return ForwardingMeasurement(
                *args, ratep=self.params.ratep, burst=self.params.burst, **kwargs
            )

        return ForwardingMeasurement_partial

    def generator_cpupin(self, flow_id: int) -> list[int]:
        """
        Needs to be round-robin, pktgen doesn't support a generator
        to be pinned to multiple CPUs. If single cpu is not sufficient,
        just create more flows with same/different src/dst IPs/ports.
        """
        return self._cpupin_based_on_policy(
            flow_id, self.params.perf_tool_cpu, "round-robin"
        )

    def _create_perf_flows(
        self,
        endpoint_pairs: list[EndpointPair[IPEndpoint]],
        perf_test: str,
        msg_size,
    ) -> list[PerfFlow]:
        """
        Same as BaseFlowMeasurementGenerator._create_perf_flows, but without
        iterating over parallel processes. This is already done by generating
        multiple perf endpoint IPs with different destination IP in ForwardingRecipe.generate_perf_endpoints.
        """
        port_iter = itertools.count(12000)

        flows = []
        for i, endpoint_pair in enumerate(endpoint_pairs):
            client, server = endpoint_pair
            server_port = client_port = next(port_iter)
            flow = self._create_perf_flow(
                perf_test,
                client.device,
                client.address,
                server_port,
                server.device,
                server.address,
                client_port,
                msg_size,
                self.generator_cpupin(i),
                self.receiver_cpupin(i),
            )
            flow.forwarder_nic = self.forwarder_ingress_nic
            # ^ there is no other (easy) way to provide forwarder nic
            # to the ForwardingMeasurement

            flows.append(flow)

        return flows

    def extract_endpoints(self, _, measurements):
        """
        :meth:`FlowEndpointsStatCPUMeasurementGenerator.extract_endpoints`
        needs to be overridden to return generator and forwarder stats.
        Receiver stats are not needed as DUT is forwarder.
        """
        endpoints = set()
        for measurement in measurements:
            if isinstance(measurement, BaseFlowMeasurement):
                for flow in measurement.flows:
                    endpoints.add(flow.generator)
                    endpoints.add(flow.forwarder_nic.netns)
        return endpoints
