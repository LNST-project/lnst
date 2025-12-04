"""
Module with implementing results container for aggregated forwarding recipes
results.

Copyright 2025 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
sdobron@redhat.com (Samuel Dobron)
"""


from lnst.RecipeCommon.Perf.Results import SequentialPerfResult
from .ForwardingMeasurementResults import ForwardingMeasurementResults
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError


class AggregatedForwardingMeasurementResults(ForwardingMeasurementResults):
    def __init__(self, measurement, flows, warmup_duration=0):
        super().__init__(measurement, True, flows, warmup_duration=warmup_duration)

        self._generator_results = SequentialPerfResult()
        self._receiver_results = SequentialPerfResult()
        self._forwarder_rx_results = SequentialPerfResult()
        self._forwarder_tx_results = SequentialPerfResult()

        self._individual_results: list[ForwardingMeasurementResults] = []

    @property
    def individual_results(self) -> list[ForwardingMeasurementResults]:
        return self._individual_results

    @property
    def measurement_success(self) -> bool:
        if self.individual_results:
            return all(res.measurement_success for res in self.individual_results)
        else:
            return False

    def add_results(self, results):
        if results is None:
            return
        elif isinstance(results, AggregatedForwardingMeasurementResults):
            self._individual_results.extend(results.individual_results)
            self.generator_results.extend(results.generator_results)
            self.receiver_results.extend(results.receiver_results)
            self.forwarder_rx_results.extend(results.forwarder_rx_results)
            self.forwarder_tx_results.extend(results.forwarder_tx_results)
        elif isinstance(results, ForwardingMeasurementResults):
            self._individual_results.append(results)
            self.generator_results.append(results.generator_results)
            self.receiver_results.append(results.receiver_results)
            self.forwarder_rx_results.append(results.forwarder_rx_results)
            self.forwarder_tx_results.append(results.forwarder_tx_results)
        else:
            raise MeasurementError("Adding incorrect results.")
