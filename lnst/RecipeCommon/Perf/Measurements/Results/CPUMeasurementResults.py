from lnst.RecipeCommon.Perf.Measurements.Results.BaseMeasurementResults import (
    BaseMeasurementResults,
)


class CPUMeasurementResults(BaseMeasurementResults):
    def __init__(self, measurement, measurement_success, host, cpu):
        super(CPUMeasurementResults, self).__init__(measurement, measurement_success)
        self._host = host
        self._cpu = cpu
        self._utilization = None

    @property
    def host(self):
        return self._host

    @property
    def cpu(self):
        return self._cpu

    @property
    def utilization(self):
        return self._utilization

    @utilization.setter
    def utilization(self, value):
        self._utilization = value

    @property
    def metrics(self) -> list[str]:
        return ['utilization']

    def describe(self):
        return "host {host} cpu '{cpu}' utilization: {average:.2f} +-{deviation:.2f} {unit} per second".format(
            host=self.host.hostid,
            cpu=self.cpu,
            average=self.utilization.average,
            deviation=self.utilization.std_deviation,
            unit=self.utilization.unit,
        )
