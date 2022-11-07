from lnst.Controller.Host import Host
from lnst.RecipeCommon.Perf.Measurements.Results.BaseMeasurementResults import BaseMeasurementResults


class LinuxPerfMeasurementResults(BaseMeasurementResults):
    _host: Host
    _filename: str
    _cpus: list[int]

    _start_timestamp: float
    _end_timestamp: float

    def __init__(
        self,
        measurement: "LinuxPerfMeasurementResults",
        host: Host,
        filename: str,
        cpus: list[int],
        start_timestamp: float,
        end_timestamp: float,
    ):
        super().__init__(measurement)
        self._host = host
        self._filename = filename
        self._cpus = cpus
        self._start_timestamp = start_timestamp
        self._end_timestamp = end_timestamp

    @property
    def host(self):
        return self._host

    @property
    def filename(self):
        return self._filename

    @property
    def cpus(self):
        return self._cpus

    @property
    def start_timestamp(self):
        return self._start_timestamp

    @property
    def end_timestamp(self):
        return self._end_timestamp

    def time_slice(self, start, end):
        return self
