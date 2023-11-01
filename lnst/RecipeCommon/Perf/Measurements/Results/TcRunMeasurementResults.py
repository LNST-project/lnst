from __future__ import annotations

from lnst.Controller.Namespace import Namespace
from lnst.Devices import Device
from lnst.RecipeCommon.Perf.Measurements.Results import BaseMeasurementResults
from lnst.RecipeCommon.Perf.Results import ParallelPerfResult


class TcRunMeasurementResults(BaseMeasurementResults):
    def __init__(
            self,
            measurement: "TcRunMeasurement",
            device: Device,
            warmup_rules=0,
    ):
        super().__init__(measurement, warmup_rules)
        self._device = device
        self._rule_install_rate: ParallelPerfResult = None
        self._run_success: bool = None

    @property
    def metrics(self) -> list[str]:
        return ['rule_install_rate']

    @property
    def device(self) -> Device:
        return self._device

    @property
    def host(self) -> Namespace:
        return self.device.host

    @property
    def rule_install_rate(self) -> ParallelPerfResult:
        return self._rule_install_rate

    @rule_install_rate.setter
    def rule_install_rate(self, result: ParallelPerfResult):
        self._rule_install_rate = result

    @property
    def run_success(self) -> bool:
        return self._run_success

    @run_success.setter
    def run_success(self, v: bool):
        self._run_success = v

    @property
    def description(self):
        return f"{self.device.host.hostid}.{self.device.name}" \
               f" tc run with {self.rule_install_rate.value} rules" \
               f" num_instances={self.measurement.num_instances}" \
               f" took {self.rule_install_rate.duration} seconds " \
               f"({self.rule_install_rate.average} rules/sec)"

    @property
    def time_taken(self):
        return self.rule_install_rate.duration

    @property
    def start_timestamp(self):
        return self.rule_install_rate.start_timestamp

    @property
    def end_timestamp(self):
        return self.rule_install_rate.end_timestamp
