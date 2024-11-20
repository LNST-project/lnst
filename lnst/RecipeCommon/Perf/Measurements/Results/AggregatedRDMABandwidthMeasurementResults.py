from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import BaseMeasurement
from lnst.RecipeCommon.Perf.Measurements.Results.RDMABandwidthMeasurementResults import RDMABandwidthMeasurementResults
from lnst.RecipeCommon.Perf.Results import SequentialPerfResult


class AggregatedRDMABandwidthMeasurementResults(RDMABandwidthMeasurementResults):
    def __init__(self, measurement: BaseMeasurement, flow: "Flow"):
        super().__init__(measurement, True, flow)
        self._individual_results = []

    @property
    def measurement_success(self) -> bool:
        if self.individual_results:
            return all(res.measurement_success for res in self.individual_results)
        else:
            return False

    @property
    def individual_results(self) -> list[RDMABandwidthMeasurementResults]:
        return self._individual_results

    @property
    def bandwidth(self) -> SequentialPerfResult:
        return SequentialPerfResult([result.bandwidth for result in self.individual_results])

    def add_results(self, result: RDMABandwidthMeasurementResults) -> None:
        self._individual_results.append(result)
