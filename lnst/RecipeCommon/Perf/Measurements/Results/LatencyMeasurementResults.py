from lnst.RecipeCommon.Perf.Results import SequentialScalarResult
from lnst.RecipeCommon.Perf.Measurements.Results.FlowMeasurementResults import (
    FlowMeasurementResults,
)
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError
from .BaseMeasurementResults import BaseMeasurementResults


class LatencyMeasurementResults(BaseMeasurementResults):
    def __init__(self, flow, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._latency_samples = (
            SequentialScalarResult()
        )  # samples are ALWAYS sequential
        self._flow = flow

    @property
    def flow(self):
        return self._flow

    @property
    def latency(self) -> SequentialScalarResult:
        return self._latency_samples

    @latency.setter
    def latency(self, value: SequentialScalarResult):
        self._latency_samples = value

    @property
    def cached_latency(self):
        return self.latency.samples_slice(slice(1, -1))

    @property
    def uncached_latency(self):
        first = self.latency.samples_slice(slice(None, 1))
        last = self.latency.samples_slice(slice(-1, None))
        merged = first.merge_with(last)

        return merged

    @property
    def metrics(self) -> list[str]:
        return ["cached_latency", "uncached_latency"]

    def add_results(self, results):
        if results is None:
            return
        if isinstance(results, LatencyMeasurementResults):
            self.latency.append(results.latency)
        else:
            raise MeasurementError("Adding incorrect results.")

    def time_slice(self, start, end):
        result_copy = LatencyMeasurementResults(self.measurement, self.flow)

        result_copy.latency = self.latency.time_slice(start, end)

        return self

    def describe(self) -> str:
        uncached_average = self.uncached_latency.average
        cached_average = self.cached_latency.average

        desc = []
        desc.append(str(self.flow))
        desc.append(
            "Generator <-> receiver cached latency (average):   {latency:>10.2f} {unit}.".format(
                latency=cached_average, unit=self.latency.unit
            )
        )
        desc.append(
            "Generator <-> receiver uncached latency (average): {latency:>10.2f} {unit}.".format(
                latency=uncached_average, unit=self.latency.unit
            )
        )
        desc.append(
            "Uncached average / cached average ratio: {ratio:.4f}".format(
                ratio=uncached_average / cached_average,
            )
        )

        return "\n".join(desc)
