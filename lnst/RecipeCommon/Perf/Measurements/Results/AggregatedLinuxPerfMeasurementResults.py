from typing import Optional
from lnst.RecipeCommon.Perf.Measurements.Results.BaseMeasurementResults import BaseMeasurementResults
from lnst.RecipeCommon.Perf.Measurements.Results.LinuxPerfMeasurementResults import LinuxPerfMeasurementResults


class AggregatedLinuxPerfMeasurementResults(BaseMeasurementResults):

    _individual_results: list[LinuxPerfMeasurementResults] = []

    def __init__(self, result: Optional[LinuxPerfMeasurementResults] = None):
        if result:
            self._individual_results = [result]

    @property
    def individual_results(self) -> list[LinuxPerfMeasurementResults]:
        return self._individual_results

    def add_results(self, result: LinuxPerfMeasurementResults):
        self._individual_results.append(result)
