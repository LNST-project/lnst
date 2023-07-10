from lnst.RecipeCommon.Perf.Measurements.Results.XDPBenchMeasurementResults import (
    XDPBenchMeasurementResults,
)
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError
from lnst.RecipeCommon.Perf.Results import SequentialPerfResult


class AggregatedXDPBenchMeasurementResults(XDPBenchMeasurementResults):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._generator_results = SequentialPerfResult()
        self._receiver_results = SequentialPerfResult()

    def add_results(self, results):
        if results is None:
            return
        elif isinstance(results, AggregatedXDPBenchMeasurementResults):
            self.generator_results.extend(results.generator_results)
            self.receiver_results.extend(results.receiver_results)
        elif isinstance(results, XDPBenchMeasurementResults):
            self.generator_results.append(results.generator_results)
            self.receiver_results.append(results.receiver_results)
        else:
            raise MeasurementError("Adding incorrect results.")
