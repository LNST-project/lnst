"""
Module with implementing results container for forwarding recipes results.

Copyright 2025 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
sdobron@redhat.com (Samuel Dobron)
"""


from .XDPBenchMeasurementResults import XDPBenchMeasurementResults
from lnst.RecipeCommon.Perf.Results import ParallelPerfResult
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError


class ForwardingMeasurementResults(XDPBenchMeasurementResults):
    """
    This is not related to a XDP measurement. However, the results
    are organized in the same way as the XDPBenchMeasurementResults.
    So this is just reusing already implemented functionality.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._forwarder_results = ParallelPerfResult()  # streams container

    @property
    def metrics(self) -> list[str]:
        return super().metrics + ["forwarder_results"]

    @property
    def forwarder_results(self) -> ParallelPerfResult:
        return self._forwarder_results

    @forwarder_results.setter
    def forwarder_results(self, value: ParallelPerfResult):
        self._forwarder_results = value

    def add_results(self, results):
        super().add_results(results)

        if results is None:
            return
        if isinstance(results, ForwardingMeasurementResults):
            self.forwarder_results.append(results.forwarder_results)
        else:
            raise MeasurementError("Adding incorrect results.")

    @property
    def start_timestamp(self):
        return min(
            [
                self.generator_results.start_timestamp,
                self.receiver_results.start_timestamp,
                self.forwarder_results.start_timestamp,
            ]
        )

    @property
    def end_timestamp(self):
        return max(
            [
                self.generator_results.end_timestamp,
                self.receiver_results.end_timestamp,
                self.forwarder_results.end_timestamp,
            ]
        )

    def time_slice(self, start, end) -> "ForwardingMeasurementResults":
        result_copy = ForwardingMeasurementResults(
            self.measurement, self.measurement_success, self.flow, warmup_duration=0
        )

        result_copy.generator_results = self.generator_results.time_slice(start, end)
        result_copy.receiver_results = self.receiver_results.time_slice(start, end)
        result_copy.forwarder_results = self.forwarder_results.time_slice(start, end)

        return result_copy

    def describe(self) -> str:
        desc = super().describe()
        desc += "\nForwarder forwarded (forwarding_results): {tput:,f} {unit} per second.".format(
            tput=self.forwarder_results.average, unit=self.forwarder_results.unit
        )

        return desc
