from lnst.RecipeCommon.Perf.Results import ParallelPerfResult
from lnst.RecipeCommon.Perf.Measurements.Results.BaseMeasurementResults import (
    BaseMeasurementResults,
)


class FlowMeasurementResults(BaseMeasurementResults):
    def __init__(self, measurement, flow, warmup_duration=0):
        super(FlowMeasurementResults, self).__init__(
            measurement, warmup_duration
        )
        self._flow = flow
        self._generator_results = None
        self._generator_cpu_stats = None
        self._receiver_results = None
        self._receiver_cpu_stats = None

    @property
    def metrics(self) -> list[str]:
        return [
            "generator_results",
            "generator_cpu_stats",
            "receiver_results",
            "receiver_cpu_stats",
        ]

    @property
    def flow(self):
        return self._flow

    @property
    def generator_results(self) -> ParallelPerfResult:
        return self._generator_results

    @generator_results.setter
    def generator_results(self, value):
        self._generator_results = value

    @property
    def generator_cpu_stats(self):
        return self._generator_cpu_stats

    @generator_cpu_stats.setter
    def generator_cpu_stats(self, value):
        self._generator_cpu_stats = value

    @property
    def receiver_results(self) -> ParallelPerfResult:
        return self._receiver_results

    @receiver_results.setter
    def receiver_results(self, value):
        self._receiver_results = value

    @property
    def receiver_cpu_stats(self):
        return self._receiver_cpu_stats

    @receiver_cpu_stats.setter
    def receiver_cpu_stats(self, value):
        self._receiver_cpu_stats = value

    @property
    def start_timestamp(self):
        return min(
            [
                self.generator_results.start_timestamp,
                self.generator_cpu_stats.start_timestamp,
                self.receiver_results.start_timestamp,
                self.receiver_cpu_stats.start_timestamp,
            ]
        )

    @property
    def end_timestamp(self):
        return max(
            [
                self.generator_results.end_timestamp,
                self.generator_cpu_stats.end_timestamp,
                self.receiver_results.end_timestamp,
                self.receiver_cpu_stats.end_timestamp,
            ]
        )

    @property
    def warmup_end(self):
        if self.warmup_duration == 0:
            return self.start_timestamp

        return max(
            [
                parallel[self.warmup_duration - 1].end_timestamp
                for parallel in (
                    *self.generator_results,
                    *self.receiver_results,
                )
            ]
        )

    @property
    def warmdown_start(self):
        if self.warmup_duration == 0:
            return self.end_timestamp

        return min(
            [
                parallel[-self.warmup_duration].start_timestamp
                for parallel in (
                    *self.generator_results,
                    *self.receiver_results,
                )
            ]
        )

    def time_slice(self, start, end):
        result_copy = FlowMeasurementResults(
            self.measurement, self.flow, warmup_duration=0
        )

        result_copy.generator_cpu_stats = self.generator_cpu_stats.time_slice(
            start, end
        )
        result_copy.receiver_cpu_stats = self.receiver_cpu_stats.time_slice(
            start, end
        )

        result_copy.generator_results = self.generator_results.time_slice(
            start, end
        )
        result_copy.receiver_results = self.receiver_results.time_slice(
            start, end
        )

        return result_copy

    def describe(self):
        generator = self.generator_results
        generator_cpu = self.generator_cpu_stats
        receiver = self.receiver_results
        receiver_cpu = self.receiver_cpu_stats
        desc = []
        desc.append(
            "Generator measured throughput: {tput:.2f} +-{deviation:.2f}({percentage:.2f}%) {unit} per second.".format(
                tput=generator.average,
                deviation=generator.std_deviation,
                percentage=self._deviation_percentage(generator),
                unit=generator.unit,
            )
        )
        desc.append(
            "Generator process CPU data: {cpu:.2f} +-{cpu_deviation:.2f} {cpu_unit} per second.".format(
                cpu=generator_cpu.average,
                cpu_deviation=generator_cpu.std_deviation,
                cpu_unit=generator_cpu.unit,
            )
        )
        desc.append(
            "Receiver measured throughput: {tput:.2f} +-{deviation:.2f}({percentage:.2f}%) {unit} per second.".format(
                tput=receiver.average,
                deviation=receiver.std_deviation,
                percentage=self._deviation_percentage(receiver),
                unit=receiver.unit,
            )
        )
        desc.append(
            "Receiver process CPU data: {cpu:.2f} +-{cpu_deviation:.2f} {cpu_unit} per second.".format(
                cpu=receiver_cpu.average,
                cpu_deviation=receiver_cpu.std_deviation,
                cpu_unit=receiver_cpu.unit,
            )
        )
        return "\n".join(desc)

    @staticmethod
    def _deviation_percentage(result):
        try:
            return (result.std_deviation / result.average) * 100
        except ZeroDivisionError:
            return float("inf") if result.std_deviation >= 0 else float("-inf")
