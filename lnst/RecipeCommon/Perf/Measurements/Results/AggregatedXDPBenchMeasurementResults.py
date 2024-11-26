from lnst.RecipeCommon.Perf.Measurements.Results.XDPBenchMeasurementResults import (
    XDPBenchMeasurementResults,
)
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError
from lnst.RecipeCommon.Perf.Results import SequentialPerfResult


class AggregatedXDPBenchMeasurementResults(XDPBenchMeasurementResults):
    def __init__(self, measurement, flow):
        super().__init__(measurement, True, flow)
        self._individual_results: list[TcRunMeasurementResults] = []
        self._generator_results = SequentialPerfResult()
        self._receiver_results = SequentialPerfResult()

    @property
    def individual_results(self) -> list[XDPBenchMeasurementResults]:
        return self._individual_results

    @property
    def measurement_success(self) -> bool:
        if self.individual_results:
            return all(res.measurement_success for res in self.individual_results)
        else:
            return False

    def add_results(self, results):
        if results is None:
            return
        elif isinstance(results, AggregatedXDPBenchMeasurementResults):
            self._individual_results.extend(results.individual_results)
            self.generator_results.extend(results.generator_results)
            self.receiver_results.extend(results.receiver_results)
        elif isinstance(results, XDPBenchMeasurementResults):
            self._individual_results.append(results)
            self.generator_results.append(results.generator_results)
            self.receiver_results.append(results.receiver_results)
        else:
            raise MeasurementError("Adding incorrect results.")
