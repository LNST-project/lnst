from lnst.RecipeCommon.Perf.Results import SequentialPerfResult
from lnst.RecipeCommon.Perf.Results import ParallelPerfResult
from lnst.RecipeCommon.Perf.Measurements.Results import CPUMeasurementResults


class StatCPUMeasurementResults(CPUMeasurementResults):
    def __init__(self, *args):
        super(StatCPUMeasurementResults, self).__init__(*args)
        self._data = {}

    def update_intervals(self, intervals):
        for key, interval in list(intervals.items()):
            if key not in self._data:
                self._data[key] = SequentialPerfResult()
            self._data[key].append(interval)

    @property
    def utilization(self):
        return ParallelPerfResult([self._data["user"], self._data["nice"],
            self._data["system"], self._data["irq"], self._data["softirq"],
            self._data["steal"]])

    @property
    def start_timestamp(self):
        return min([item.start_timestamp for item in self._data.values()])

    @property
    def end_timestamp(self):
        return max([item.end_timestamp for item in self._data.values()])

    def time_slice(self, start, end):
        result_copy = StatCPUMeasurementResults(
                self.measurement,
                self.measurement_success,
                self.host,
                self.cpu
                )
        for cpu_state, intervals in self._data.items():
            result_copy._data[cpu_state] = intervals.time_slice(start, end)
        return result_copy
