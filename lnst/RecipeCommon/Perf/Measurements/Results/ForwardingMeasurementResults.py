"""
Module with implementing results container for forwarding recipes results.

Copyright 2025 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
sdobron@redhat.com (Samuel Dobron)
"""

from itertools import chain

from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import Flow
from lnst.RecipeCommon.Perf.Results import SequentialPerfResult, ParallelPerfResult
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError
from lnst.RecipeCommon.Perf.Measurements.Results.BaseMeasurementResults import (
    BaseMeasurementResults,
)


class ForwardingMeasurementResults(BaseMeasurementResults):
    """
    Results container for forwarding measurements.

    This tracks results for all flows together:
    - generator_results: ParallelPerfResult containing per-flow results
    - receiver_results: SequentialPerfResult (per-measurement, all flows combined)
    - forwarder_rx_results: SequentialPerfResult (per-measurement, RX packets)
    - forwarder_tx_results: SequentialPerfResult (per-measurement, TX packets)
    """

    def __init__(self, measurement, measurement_success, flows, warmup_duration=0):
        super().__init__(measurement, measurement_success, warmup_duration)

        self._flows = flows
        self._generator_results = ParallelPerfResult()
        self._receiver_results = SequentialPerfResult()
        self._forwarder_rx_results = SequentialPerfResult()
        self._forwarder_tx_results = SequentialPerfResult()

    @property
    def flows(self):
        return self._flows

    @property
    def metrics(self) -> list[str]:
        return [
            "generator_results",
            "receiver_results",
            "forwarder_rx_results",
            "forwarder_tx_results",
        ]

    @property
    def generator_results(self) -> ParallelPerfResult:
        return self._generator_results

    @generator_results.setter
    def generator_results(self, value: ParallelPerfResult):
        self._generator_results = value

    @property
    def receiver_results(self) -> SequentialPerfResult:
        return self._receiver_results

    @receiver_results.setter
    def receiver_results(self, value: SequentialPerfResult):
        self._receiver_results = value

    @property
    def forwarder_rx_results(self) -> SequentialPerfResult:
        return self._forwarder_rx_results

    @forwarder_rx_results.setter
    def forwarder_rx_results(self, value: SequentialPerfResult):
        self._forwarder_rx_results = value

    @property
    def forwarder_tx_results(self) -> SequentialPerfResult:
        return self._forwarder_tx_results

    @forwarder_tx_results.setter
    def forwarder_tx_results(self, value: SequentialPerfResult):
        self._forwarder_tx_results = value

    @property
    def start_timestamp(self):
        return min(
            [
                self.generator_results.start_timestamp,
                self.receiver_results.start_timestamp,
                self.forwarder_rx_results.start_timestamp,
                self.forwarder_tx_results.start_timestamp,
            ]
        )

    @property
    def end_timestamp(self):
        return max(
            [
                self.generator_results.end_timestamp,
                self.receiver_results.end_timestamp,
                self.forwarder_rx_results.end_timestamp,
                self.forwarder_tx_results.end_timestamp,
            ]
        )

    @property
    def warmup_end(self):
        return self.start_timestamp + self.warmup_duration

    @property
    def warmdown_start(self):
        return self.end_timestamp - self.warmup_duration

    def time_slice(self, start, end) -> "ForwardingMeasurementResults":
        result_copy = ForwardingMeasurementResults(
            self.measurement, self.measurement_success, self.flows, warmup_duration=0
        )

        result_copy.generator_results = self.generator_results.time_slice(start, end)
        result_copy.receiver_results = self.receiver_results.time_slice(start, end)
        result_copy.forwarder_rx_results = self.forwarder_rx_results.time_slice(
            start, end
        )
        result_copy.forwarder_tx_results = self.forwarder_tx_results.time_slice(
            start, end
        )

        return result_copy

    def add_results(self, results):
        """Add results from another ForwardingMeasurementResults instance."""
        if results is None:
            return
        if isinstance(results, ForwardingMeasurementResults):
            self.generator_results.extend(results.generator_results)
            self.receiver_results.extend(results.receiver_results)
            self.forwarder_rx_results.extend(results.forwarder_rx_results)
            self.forwarder_tx_results.extend(results.forwarder_tx_results)
        else:
            raise MeasurementError("Adding incorrect results.")

    def _transpose_generator_results(self):
        """
        Transpose generator results from iterations-of-flows to flows-of-iterations.
        """
        generator = self.generator_results

        num_flows = len(self.flows)
        transposed = ParallelPerfResult()

        for flow_idx in range(num_flows):
            flow_iterations = SequentialPerfResult()
            for iteration in generator:
                flow_iterations.append(iteration[flow_idx])
            transposed.append(flow_iterations)

        return transposed

    def describe(self) -> str:
        receiver = self.receiver_results
        generator = self.generator_results

        desc = []

        transposed_generator = self._transpose_generator_results()

        if len(self.flows) > 1:
            for flow, gen_results in zip(self.flows, transposed_generator):
                desc.append(str(flow))
                desc.append(
                    "Generator generated (generator_results): {tput:_.2f} +-{deviation:.2f}({percentage:.2f}%) {unit} per second.".format(
                        tput=gen_results.average,
                        deviation=gen_results.std_deviation,
                        percentage=self._deviation_percentage(gen_results),
                        unit=gen_results.unit,
                    ).replace("_", " ")
                )

        desc.append(str(self.flow))
        desc.append(
            "Generator generated (generator_results): {tput:_.2f} +-{deviation:.2f}({percentage:.2f}%) {unit} per second.".format(
                tput=generator.average,
                deviation=generator.std_deviation,
                percentage=self._deviation_percentage(generator),
                unit=generator.unit,
            ).replace("_", " ")
        )
        desc.append(
            "Receiver processed (receiver_results): {tput:_.2f} +-{deviation:.2f}({percentage:.2f}%) {unit} per second.".format(
                tput=receiver.average,
                deviation=receiver.std_deviation,
                percentage=self._deviation_percentage(receiver),
                unit=receiver.unit,
            ).replace("_", " ")
        )
        desc.append(
            "Forwarder RX (forwarder_rx_results): {tput:_.2f} +-{deviation:.2f}({percentage:.2f}%) {unit} per second.".format(
                tput=self.forwarder_rx_results.average,
                deviation=self.forwarder_rx_results.std_deviation,
                percentage=self._deviation_percentage(self.forwarder_rx_results),
                unit=self.forwarder_rx_results.unit,
            ).replace("_", " ")
        )
        desc.append(
            "Forwarder TX (forwarder_tx_results): {tput:_.2f} +-{deviation:.2f}({percentage:.2f}%) {unit} per second.".format(
                tput=self.forwarder_tx_results.average,
                deviation=self.forwarder_tx_results.std_deviation,
                percentage=self._deviation_percentage(self.forwarder_tx_results),
                unit=self.forwarder_tx_results.unit,
            ).replace("_", " ")
        )

        return "\n".join(desc)

    @staticmethod
    def _deviation_percentage(result):
        try:
            return (result.std_deviation / result.average) * 100
        except ZeroDivisionError:
            return float("inf") if result.std_deviation >= 0 else float("-inf")

    @property
    def flow(self):
        first_flow = self.flows[0]
        generator_cpupins = list(
            chain.from_iterable(flow.generator_cpupin for flow in self.flows)
        )
        receiver_cpupins = list(
            chain.from_iterable(flow.receiver_cpupin for flow in self.flows)
        )

        return Flow(
            type=first_flow.type,
            generator=first_flow.generator,
            generator_bind=first_flow.generator_bind,
            generator_nic=first_flow.generator_nic,
            receiver=first_flow.receiver,
            receiver_bind=None,
            receiver_nic=first_flow.receiver_nic,
            receiver_port=None,
            msg_size=first_flow.msg_size,
            duration=first_flow.duration,
            parallel_streams=len(self.flows),
            generator_cpupin=generator_cpupins,
            receiver_cpupin=receiver_cpupins,
            aggregated_flow=True,
            warmup_duration=first_flow.warmup_duration,
        )
