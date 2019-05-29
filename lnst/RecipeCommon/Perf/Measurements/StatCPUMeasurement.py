import signal

from lnst.Controller.RecipeResults import ResultLevel
from lnst.RecipeCommon.Perf.Results import PerfInterval
from lnst.RecipeCommon.Perf.Results import SequentialPerfResult
from lnst.RecipeCommon.Perf.Results import ParallelPerfResult
from lnst.RecipeCommon.Perf.Measurements.BaseCPUMeasurement import BaseCPUMeasurement
from lnst.RecipeCommon.Perf.Measurements.BaseCPUMeasurement import CPUMeasurementResults

from lnst.Tests.CPUStatMonitor import CPUStatMonitor

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

class StatCPUMeasurement(BaseCPUMeasurement):
    def __init__(self, *args):
        super(StatCPUMeasurement, self).__init__(*args)
        self._running_measurements = []
        self._finished_measurements = []

    @property
    def version(self):
        return "1"

    def start(self):
        jobs = []
        for host in self._conf:
            jobs.append(
                host.run(
                    CPUStatMonitor(interval=1000),
                    bg=True,
                    job_level=ResultLevel.NORMAL,
                )
            )
        self._running_measurements = jobs

    def finish(self):
        jobs = self._running_measurements
        try:
            for job in jobs:
                job.kill(signal.SIGINT)
                job.wait()
        finally:
            for job in jobs:
                job.kill()

        self._running_measurements = []
        self._finished_measurements = jobs

    def collect_results(self):
        results = []
        for job in self._finished_measurements:
            job_results = self._process_job(job)
            results.extend(job_results)

        return results

    def _process_job(self, job):
        host = job.host
        job_results = {}
        for sample in job.result["data"]:
            parsed_sample = self._parse_sample(sample)

            for cpu, cpu_intervals in list(parsed_sample.items()):
                if cpu not in job_results:
                    job_results[cpu] = StatCPUMeasurementResults(self, host, cpu)
                cpu_results = job_results[cpu]
                cpu_results.update_intervals(cpu_intervals)

        return list(job_results.values())

    def _parse_sample(self, sample):
        result = {}
        duration = sample["duration"]
        for key, value in list(sample.items()):
            if key.startswith("cpu"):
                result[key] = self._create_cpu_intervals(duration, value)
        return result

    def _create_cpu_intervals(self, duration, cpu_intervals):
        result = {}
        for key, value in list(cpu_intervals.items()):
            result[key] = PerfInterval(value, duration, "time units")
        return result
