from __future__ import annotations

from lnst.Controller.Namespace import Namespace
from lnst.Devices import Device
from lnst.RecipeCommon.Perf.Measurements.Results import BaseMeasurementResults
from lnst.RecipeCommon.Perf.Results import PerfInterval


class TcRunMeasurementResults(BaseMeasurementResults):
    def __init__(
            self,
            measurement: "TcRunMeasurement",
            device: Device,
            warmup_rules=0,
    ):
        super().__init__(measurement, warmup_rules)
        self._device = device
        self._run_interval: PerfInterval = None
        self._run_success: bool = None

    @property
    def device(self) -> Device:
        return self._device

    @property
    def host(self) -> Namespace:
        return self.device.host

    @property
    def run_interval(self) -> PerfInterval:
        return self._run_interval

    @property
    def run_success(self) -> bool:
        return self._run_success

    @run_success.setter
    def run_success(self, v: bool):
        self._run_success = v

    @run_interval.setter
    def run_interval(self, interval: PerfInterval):
        self._run_interval = interval

    @property
    def description(self):
        return f"{self.device.host.hostid}.{self.device.name}" \
               f" tc run with {self.run_interval.value} rules" \
               f" took {self.run_interval.duration} seconds"

    @property
    def time_taken(self):
        return self.run_interval.duration

    @property
    def start_timestamp(self):
        return self.run_interval.start_timestamp

    @property
    def end_timestamp(self):
        return self.run_interval.end_timestamp
