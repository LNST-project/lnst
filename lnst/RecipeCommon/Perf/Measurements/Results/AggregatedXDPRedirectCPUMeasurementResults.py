from lnst.RecipeCommon.Perf.Results import SequentialPerfResult
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError
from lnst.RecipeCommon.Perf.Measurements.Results.XDPRedirectCPUMeasurementResults import (
    XDPRedirectCPUMeasurementResults,
)


class AggregatedXDPRedirectCPUMeasurementResults(XDPRedirectCPUMeasurementResults):
    def __init__(self, measurement, flows):
        super().__init__(measurement, True, flows)
        self._individual_results: list[XDPRedirectCPUMeasurementResults] = []
        self._generator_results = SequentialPerfResult()
        self._receiver_results = SequentialPerfResult()
        self._forwarded_results = SequentialPerfResult()

    @property
    def individual_results(self) -> list[XDPRedirectCPUMeasurementResults]:
        return self._individual_results

    @property
    def measurement_success(self) -> bool:
        if self._individual_results:
            return all(res.measurement_success for res in self._individual_results)
        return False

    def add_results(self, results):
        if results is None:
            return
        elif isinstance(results, AggregatedXDPRedirectCPUMeasurementResults):
            self._individual_results.extend(results.individual_results)
            self.generator_results.extend(results.generator_results)
            self.receiver_results.extend(results.receiver_results)
            self.forwarded_results.extend(results.forwarded_results)
        elif isinstance(results, XDPRedirectCPUMeasurementResults):
            self._individual_results.append(results)
            self.generator_results.append(results.generator_results)
            self.receiver_results.append(results.receiver_results)
            self.forwarded_results.append(results.forwarded_results)
        else:
            raise MeasurementError("Adding incorrect results.")
