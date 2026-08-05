from itertools import chain

from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import Flow
from lnst.RecipeCommon.Perf.Results import ParallelPerfResult
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError
from lnst.RecipeCommon.Perf.Measurements.Results.XDPBenchMeasurementResults import (
    XDPBenchMeasurementResults,
)


class XDPRedirectCPUMeasurementResults(XDPBenchMeasurementResults):
    """
    Results container for XDP redirect-cpu measurements.

    Extends :class:`XDPBenchMeasurementResults` with per-CPU receiver stats.

    Metrics:

    - ``generator_results``: :class:`ParallelPerfResult` — pktgen per-flow stats
    - ``receiver_results``: :class:`ParallelPerfResult` — one
      :class:`SequentialPerfResult` per target CPU, from xdp-bench
      ``kthread cpu:N pkt/s`` (packets dequeued by each target CPU's kthread)
    - ``forwarded_results``: :class:`ParallelPerfResult` — single
      :class:`SequentialPerfResult` inside, from xdp-bench
      ``receive total pkt/s`` (packets received and forwarded by the IRQ CPU)

    :param flows: list of individual :class:`Flow` objects covered by this
        result (one per pktgen instance)
    """

    def __init__(self, measurement, measurement_success, flows, warmup_duration=0):
        super().__init__(measurement, measurement_success, None, warmup_duration)
        self._flows = flows
        self._forwarded_results = ParallelPerfResult()

    @property
    def flows(self):
        return self._flows

    @property
    def flow(self):
        first_flow = self._flows[0]
        generator_cpupins = list(
            chain.from_iterable(flow.generator_cpupin for flow in self._flows)
        )
        receiver_cpupins = list(
            chain.from_iterable(
                flow.receiver_cpupin
                for flow in self._flows
                if flow.receiver_cpupin
            )
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
            parallel_streams=len(self._flows),
            generator_cpupin=generator_cpupins,
            receiver_cpupin=receiver_cpupins or None,
            aggregated_flow=True,
            warmup_duration=first_flow.warmup_duration,
        )

    @property
    def metrics(self) -> list[str]:
        return super().metrics + ["forwarded_results"]

    @property
    def forwarded_results(self) -> ParallelPerfResult:
        return self._forwarded_results

    @forwarded_results.setter
    def forwarded_results(self, value: ParallelPerfResult):
        self._forwarded_results = value

    @property
    def start_timestamp(self):
        timestamps = [super().start_timestamp]
        if self._forwarded_results:
            timestamps.append(self._forwarded_results.start_timestamp)
        return min(timestamps)

    @property
    def end_timestamp(self):
        timestamps = [super().end_timestamp]
        if self._forwarded_results:
            timestamps.append(self._forwarded_results.end_timestamp)
        return max(timestamps)

    def time_slice(self, start, end) -> "XDPRedirectCPUMeasurementResults":
        result_copy = XDPRedirectCPUMeasurementResults(
            self.measurement, self.measurement_success, self._flows, warmup_duration=0
        )
        result_copy.generator_results = self.generator_results.time_slice(start, end)
        result_copy.receiver_results = self.receiver_results.time_slice(start, end)
        result_copy.forwarded_results = self.forwarded_results.time_slice(start, end)
        return result_copy

    def add_results(self, results):
        if results is None:
            return
        if isinstance(results, XDPRedirectCPUMeasurementResults):
            super().add_results(results)
            self.forwarded_results.extend(results.forwarded_results)
        else:
            raise MeasurementError("Adding incorrect results.")

    def describe(self) -> str:
        generator = self.generator_results
        receiver = self.receiver_results
        forwarded = self.forwarded_results

        desc = [str(self.flow)]
        desc.append(
            "Generator generated (generator_results): {tput:,f} +-{deviation:,f}({percentage:.2f}%) {unit} per second.".format(
                tput=generator.average,
                deviation=generator.std_deviation,
                percentage=generator.deviation_percentage,
                unit=generator.unit,
            )
        )
        if forwarded:
            desc.append(
                "IRQ CPU forwarded (forwarded_results): {tput:,f} +-{deviation:,f}({percentage:.2f}%) {unit} per second.".format(
                    tput=forwarded.average,
                    deviation=forwarded.std_deviation,
                    percentage=forwarded.deviation_percentage,
                    unit=forwarded.unit,
                )
            )
        if receiver:
            desc.append(
                "Per-CPU received (receiver_results): {tput:,f} +-{deviation:,f}({percentage:.2f}%) {unit} per second.".format(
                    tput=receiver.average,
                    deviation=receiver.std_deviation,
                    percentage=receiver.deviation_percentage,
                    unit=receiver.unit,
                )
            )
        return "\n".join(desc)
