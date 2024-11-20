from lnst.RecipeCommon.Perf.Results import ParallelPerfResult
from lnst.RecipeCommon.Perf.Measurements.Results.BaseMeasurementResults import (
    BaseMeasurementResults,
)
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError


class XDPBenchMeasurementResults(BaseMeasurementResults):
    def __init__(self, measurement, measurement_success, flow, warmup_duration=0):
        super().__init__(measurement, measurement_success, warmup_duration)

        self._flow = flow

        self._generator_results = ParallelPerfResult()  # multiple instances of pktgen
        self._receiver_results = ParallelPerfResult()  # single instance of xdpbench

    @property
    def flow(self):
        return self._flow

    @property
    def metrics(self) -> list[str]:
        return ['generator_results', 'receiver_results']

    @property
    def generator_results(self) -> ParallelPerfResult:
        return self._generator_results

    @generator_results.setter
    def generator_results(self, value: ParallelPerfResult):
        self._generator_results = value

    @property
    def receiver_results(self) -> ParallelPerfResult:
        return self._receiver_results

    @receiver_results.setter
    def receiver_results(self, value: ParallelPerfResult):
        self._receiver_results = value

    def add_results(self, results):
        if results is None:
            return
        if isinstance(results, XDPBenchMeasurementResults):
            self.generator_results.append(results.generator_results)
            self.receiver_results.append(results.receiver_results)
        else:
            raise MeasurementError("Adding incorrect results.")

    @property
    def start_timestamp(self):
        return min(
            [
                self.generator_results.start_timestamp,
                self.receiver_results.start_timestamp,
            ]
        )

    @property
    def end_timestamp(self):
        return max(
            [
                self.generator_results.end_timestamp,
                self.receiver_results.end_timestamp,
            ]
        )

    @property
    def warmup_end(self):
        return self.start_timestamp+self.warmup_duration

    @property
    def warmdown_start(self):
        return self.end_timestamp-self.warmup_duration

    def time_slice(self, start, end) -> "XDPBenchMeasurementResults":
        result_copy = XDPBenchMeasurementResults(
            self.measurement, self.measurement_success, self.flow, warmup_duration=0
        )

        result_copy.generator_results = self.generator_results.time_slice(start, end)
        result_copy.receiver_results = self.receiver_results.time_slice(start, end)

        return result_copy

    def describe(self) -> str:
        generator = self.generator_results
        receiver = self.receiver_results

        desc = []
        desc.append(str(self.flow))
        desc.append(
            "Generator generated (generator_results): {tput:,f} {unit} per second.".format(
                tput=generator.average, unit=generator.unit
            )
        )
        desc.append(
            "Receiver processed (receiver_results): {tput:,f} {unit} per second.".format(
                tput=receiver.average, unit=receiver.unit
            )
        )

        return "\n".join(desc)
