from __future__ import annotations
from typing import Union

from lnst.Devices import Device
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError
from lnst.RecipeCommon.Perf.Measurements.Results.TcRunMeasurementResults import TcRunMeasurementResults
from lnst.RecipeCommon.Perf.Results import SequentialPerfResult


class AggregatedTcRunMeasurementResults(TcRunMeasurementResults):

    def __init__(
            self,
            measurement: "TcRunMeasurement",
            device: Device,
            warmup_rules=0,
    ):
        super().__init__(measurement, device, warmup_rules=warmup_rules)
        self._individual_results: list[TcRunMeasurementResults] = []
        self._rule_install_rate: SequentialPerfResult = SequentialPerfResult()

    @property
    def rule_install_rate(self) -> SequentialPerfResult:
        return self._rule_install_rate

    @rule_install_rate.setter
    def rule_install_rate(self, result: SequentialPerfResult):
        self._rule_install_rate = result

    @property
    def run_success(self) -> bool:
        return all((i.run_success for i in self.individual_results))

    @property
    def individual_results(self) -> list[TcRunMeasurementResults]:
        return self._individual_results

    def add_results(self, result: Union[AggregatedTcRunMeasurementResults, TcRunMeasurementResults]):
        if result is None:
            return
        elif isinstance(result, AggregatedTcRunMeasurementResults):
            self._individual_results.extend(result.individual_results)
            self._rule_install_rate.extend(result.rule_install_rate)
        elif isinstance(result, TcRunMeasurementResults):
            self._individual_results.append(result)
            self._rule_install_rate.append(result.rule_install_rate)
        else:
            raise MeasurementError("Adding incorrect results.")
