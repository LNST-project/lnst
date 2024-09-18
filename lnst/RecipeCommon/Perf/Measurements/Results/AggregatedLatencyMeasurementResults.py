from .LatencyMeasurementResults import LatencyMeasurementResults

from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError
from lnst.RecipeCommon.Perf.Results import ParallelScalarResult


class AggregatedLatencyMeasurementResults(LatencyMeasurementResults):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._latency_samples = ParallelScalarResult()  # container for parallel measurements

    def add_results(self, results):
        if results is None:
            return
        elif isinstance(results, AggregatedLatencyMeasurementResults):
            self.latency.extend(results.latency)
        elif isinstance(results, LatencyMeasurementResults):
            self.latency.append(results.latency)
        else:
            raise MeasurementError("Adding incorrect results.")

