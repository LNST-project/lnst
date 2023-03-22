from __future__ import annotations
from statistics import mean
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

    @property
    def description(self):
        return f"{self.device.host.hostid}.{self.device.name} multi tc run" \
               f" num_instances={self.num_instances}"\
               f" mean time_taken={self.time_taken}s" \
               f" num_rules={self.num_rules}"

    @property
    def rule_install_rate(self) -> SequentialPerfResult:
        return SequentialPerfResult([i.rule_install_rate for i in self.individual_results])

    @property
    def time_taken(self) -> float:
        # Return average time for all runs
        return mean([i.duration for i in self.rule_install_rate])

    @property
    def num_rules(self) -> tuple[int]:
        return tuple([r.value for r in self.rule_install_rate])

    @property
    def num_instances(self):
        return len(self.individual_results)

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
            self._individual_results.extend([r for r in result.individual_results])
        elif isinstance(result, TcRunMeasurementResults):
            self._individual_results.append(result)
        else:
            raise MeasurementError("Adding incorrect results.")
