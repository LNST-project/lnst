from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import BaseMeasurement
from lnst.RecipeCommon.Perf.Measurements.Results.BaseMeasurementResults import BaseMeasurementResults
from lnst.RecipeCommon.Perf.Results import PerfInterval, PerfResult


class RDMABandwidthMeasurementResults(BaseMeasurementResults):
    def __init__(self, measurement: BaseMeasurement, flow: "Flow"):
        super().__init__(measurement)

        self._flow = flow

    @property
    def metrics(self) -> list[str]:
        return ['bandwidth']

    @property
    def flow(self):
        return self._flow

    @property
    def bandwidth(self) -> PerfInterval:
        return self._bandwidth

    @bandwidth.setter
    def bandwidth(self, bandwidth: PerfInterval) -> None:
        self._bandwidth = bandwidth

    @property
    def start_timestamp(self):
        return self._bandwidth.start_timestamp

    @property
    def end_timestamp(self):
        return self._bandwidth.end_timestamp

    def time_slice(self, start, end):
        result_copy = RDMABandwidthMeasurementResults(self.measurement, self.flow)
        result_copy.bandwidth = self.bandwidth.time_slice(start, end)
        return result_copy

    def describe(self) -> str:
        bw = self.bandwidth
        return "ib_send_bw measured bandwidth: {avg:.2f} +-{stddev:.2f}({percentage:.2f}%) MiB/s.".format(
            avg=bw.average,
            stddev=bw.std_deviation,
            percentage=self._deviation_percentage(bw),
        )

    @classmethod
    def _deviation_percentage(cls, result: PerfResult) -> float:
        try:
            return (result.std_deviation/result.average) * 100
        except ZeroDivisionError:
            return float('inf') if result.std_deviation >= 0 else float("-inf")
