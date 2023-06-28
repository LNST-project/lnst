from lnst.RecipeCommon.Perf.Measurements import BaseMeasurement


class BaseMeasurementResults(object):
    def __init__(self, measurement: BaseMeasurement, warmup=0):
        self._measurement = measurement
        self._warmup_duration = warmup

    @property
    def measurement(self) -> BaseMeasurement:
        return self._measurement

    @property
    def warmup_duration(self):
        return self._warmup_duration

    def align_data(self, start, end):
        return self

    def describe(self):
        return ""
