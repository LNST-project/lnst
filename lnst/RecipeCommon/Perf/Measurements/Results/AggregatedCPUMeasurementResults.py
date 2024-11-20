from lnst.RecipeCommon.Perf.Results import SequentialPerfResult
from lnst.RecipeCommon.Perf.Measurements.Results.CPUMeasurementResults import CPUMeasurementResults
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError


class AggregatedCPUMeasurementResults(CPUMeasurementResults):
    def __init__(self, measurement, host, cpu):
        super(AggregatedCPUMeasurementResults, self).__init__(measurement, True, host, cpu)
        self._individual_results = []

    @property
    def measurement_success(self) -> bool:
        if self.individual_results:
            return all(res.measurement_success for res in self.individual_results)
        else:
            return False

    @property
    def individual_results(self):
        return self._individual_results

    @property
    def utilization(self):
        return SequentialPerfResult([i.utilization
                                     for i in self.individual_results])

    def add_results(self, results):
        if results is None:
            return
        elif isinstance(results, AggregatedCPUMeasurementResults):
            self.individual_results.extend(results.individual_results)
        elif isinstance(results, CPUMeasurementResults):
            self.individual_results.append(results)
        else:
            raise MeasurementError("Adding incorrect results.")
