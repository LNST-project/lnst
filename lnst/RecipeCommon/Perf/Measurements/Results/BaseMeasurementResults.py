from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import BaseMeasurement


class BaseMeasurementResults(object):
    def __init__(self, measurement: BaseMeasurement, measurement_success=True, warmup=0):
        self._measurement = measurement
        self._measurement_success = measurement_success
        self._warmup_duration = warmup

    @property
    def measurement(self) -> BaseMeasurement:
        return self._measurement

    @property
    def measurement_success(self) -> bool:
        return self._measurement_success

    @property
    def warmup_duration(self):
        return self._warmup_duration

    @property
    def metrics(self) -> list[str]:
        return []

    def align_data(self, start, end):
        return self

    def describe(self):
        return ""
