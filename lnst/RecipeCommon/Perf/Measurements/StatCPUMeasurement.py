import signal

from lnst.Controller.RecipeResults import ResultLevel
from lnst.RecipeCommon.Perf.Results import PerfInterval
from lnst.RecipeCommon.Perf.Measurements.BaseCPUMeasurement import BaseCPUMeasurement
from lnst.RecipeCommon.Perf.Measurements.Results import StatCPUMeasurementResults

from lnst.Tests.CPUStatMonitor import CPUStatMonitor


class StatCPUMeasurement(BaseCPUMeasurement):
    def __init__(self, hosts, recipe_conf=None):
        super(StatCPUMeasurement, self).__init__(recipe_conf)
        self._hosts = hosts
        self._running_measurements = []
        self._finished_measurements = []

    @property
    def version(self):
        return "1"

    @property
    def hosts(self):
        return self._hosts

    def start(self):
        jobs = []
        for host in sorted(self.hosts, key=lambda x: x.hostid):
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
        timestamp = sample["timestamp"]
        for key, value in list(sample.items()):
            if key.startswith("cpu"):
                result[key] = self._create_cpu_intervals(duration, value, timestamp)
        return result

    def _create_cpu_intervals(self, duration, cpu_intervals, timestamp):
        result = {}
        for key, value in list(cpu_intervals.items()):
            result[key] = PerfInterval(value, duration, "time units", timestamp)
        return result
