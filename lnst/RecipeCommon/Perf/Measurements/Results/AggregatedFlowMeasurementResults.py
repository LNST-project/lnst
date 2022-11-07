from lnst.RecipeCommon.Perf.Results import SequentialPerfResult
from lnst.RecipeCommon.Perf.Measurements.Results.FlowMeasurementResults import FlowMeasurementResults
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError


class AggregatedFlowMeasurementResults(FlowMeasurementResults):
    def __init__(self, measurement, flow):
        super(FlowMeasurementResults, self).__init__(measurement)
        self._flow = flow
        self._generator_results = SequentialPerfResult()
        self._generator_cpu_stats = SequentialPerfResult()
        self._receiver_results = SequentialPerfResult()
        self._receiver_cpu_stats = SequentialPerfResult()
        self._individual_results = []

    @property
    def individual_results(self):
        return self._individual_results

    def add_results(self, results):
        if results is None:
            return
        elif isinstance(results, AggregatedFlowMeasurementResults):
            self.individual_results.extend(results.individual_results)
            self.generator_results.extend(results.generator_results)
            self.generator_cpu_stats.extend(results.generator_cpu_stats)
            self.receiver_results.extend(results.receiver_results)
            self.receiver_cpu_stats.extend(results.receiver_cpu_stats)
        elif isinstance(results, FlowMeasurementResults):
            self.individual_results.append(results)
            self.generator_results.append(results.generator_results)
            self.generator_cpu_stats.append(results.generator_cpu_stats)
            self.receiver_results.append(results.receiver_results)
            self.receiver_cpu_stats.append(results.receiver_cpu_stats)
        else:
            raise MeasurementError("Adding incorrect results.")
