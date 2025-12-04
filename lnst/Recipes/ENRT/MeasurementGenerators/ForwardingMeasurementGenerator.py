"""
Module with generator class for Forwarding Recipe.

Copyright 2025 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
sdobron@redhat.com (Samuel Dobron)
"""

from lnst.Recipes.ENRT.MeasurementGenerators.BaseFlowMeasurementGenerator import (
    BaseFlowMeasurementGenerator,
)
from lnst.RecipeCommon.Perf.Measurements.ForwardingMeasurement import (
    ForwardingMeasurement,
)
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import BaseFlowMeasurement


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
        :class:`ForwardingMeasurement` sets up :class:`InterfaceStatsMonitor`
        on `Flow.forwarder_nic`. So, either parent class needs to set it
        or it needs to be set here.
        """
        flows = super()._create_perf_flows(endpoint_pairs, perf_test, msg_size)
        for flow in flows:
            flow.forwarder_rx_nic = self.forwarder_ingress_nic
            flow.forwarder_tx_nic = self.forwarder_egress_nic

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
                    endpoints.add(flow.forwarder_rx_nic.netns)
        return endpoints
