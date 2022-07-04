from typing import Any, Optional, Iterable
from datetime import datetime
import logging
import signal
import time
import os
import re

from lnst.Tests.LinuxPerf import LinuxPerf
from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import (
    BaseMeasurement,
    BaseMeasurementResults,
)
from lnst.Controller.Job import Job
from lnst.Controller.Host import Host
from lnst.Controller.Recipe import BaseRecipe
from lnst.Controller.RecipeResults import ResultLevel, ResultType

def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H:%M:%S")

class LinuxPerfMeasurementResults(BaseMeasurementResults):
    _host: Host
    _filename: str
    _cpus: list[int]

    _start_timestamp: float
    _end_timestamp: float

    def __init__(
        self,
        measurement: "LinuxPerfMeasurement",
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


class AggregatedLinuxPerfMeasurementResults(BaseMeasurementResults):

    _individual_results: list[LinuxPerfMeasurementResults] = []

    def __init__(self, result: Optional[LinuxPerfMeasurementResults] = None):
        if result:
            self._individual_results = [result]

    @property
    def individual_results(self) -> list[LinuxPerfMeasurementResults]:
        return self._individual_results

    def add_results(self, result: LinuxPerfMeasurementResults):
        self._individual_results.append(result)


class LinuxPerfMeasurement(BaseMeasurement):
    _MEASUREMENT_VERSION: int = 1

    hosts: list[Host]
    linuxperf_cpus: list[list[int]]
    _start_timestamp: float
    _end_timestamp: float
    _data_folder: str

    _version: Optional[dict[str, Any]] = None
    _collection_index: int = 0
    _jobs: list[Job] = []

    def __init__(
        self,
        hosts: list[Host],
        linuxperf_cpus: list[list[int]],
        data_folder: str,
        recipe_conf: Any = None,
    ):
        super().__init__(recipe_conf)

        self.hosts = hosts
        self.linuxperf_cpus = linuxperf_cpus
        self._data_folder = data_folder

        # create output folders
        for host in self.hosts:
            try:
                os.mkdir(os.path.join(self._data_folder, host.hostid))
            except FileExistsError:
                pass

    @property
    def version(self) -> Optional[dict[str, Any]]:
        if self._version:
            return self._version

        perf_version: Optional[str] = self._get_host_perf_version()
        if perf_version is None:
            return None

        self._version = {
            "measurement_version": self._MEASUREMENT_VERSION,
            "host_perf_version": perf_version,
        }
        return self._version

    def _get_host_perf_version(self) -> Optional[str]:
        if not len(self.hosts):
            raise Exception(
                "No hosts in LinuxPerfMeasurement while getting perf version"
            )

        version_job = self.hosts[0].run("perf --version", job_level=ResultLevel.DEBUG)
        if version_job.passed:
            match = re.match(r"perf version (.+?)", version_job.stdout)
            if match:
                return match.group(1)
        return None

    @property
    def configurations(self) -> Iterable[tuple[Host, list[int]]]:
        for host in self.hosts:
            for cpu_list in self.linuxperf_cpus:
                yield (host, cpu_list)

    def start(self) -> None:
        self._start_timestamp = time.time()
        for host, cpus in self.configurations:
            filename: str = f"cpus.{'.'.join(map(str, cpus))}.data"
            self._jobs.append(host.run(LinuxPerf(output_file=filename, cpus=cpus), bg=True))

    def finish(self) -> None:
        for job, (host, _) in zip(self._jobs, self.configurations):
            job.kill(signal=signal.SIGINT)
            if not job.wait(timeout=120):
                logging.error(f"timeout while waiting for linuxperf job to finish on host {host.hostid}")
        self._end_timestamp = time.time()

    def collect_results(self) -> list[BaseMeasurementResults]:
        self._collection_index += 1
        results: list[BaseMeasurementResults] = []
        for job, (host, cpus) in zip(self._jobs, self.configurations):
            if job.result is None:
                continue

            # copy agent's perf.data file to a controller
            src_filepath: str = job.result["filename"]
            new_filename: str = f"{os.path.basename(src_filepath)}.{self._collection_index}.{timestamp()}"
            dst_filepath: str = os.path.join(self._data_folder, host.hostid, new_filename)

            host.copy_file_from_machine(src_filepath, dst_filepath)
            logging.debug(f"perf-record data copied from agent to {dst_filepath}")
            results.append(
                LinuxPerfMeasurementResults(
                    self,
                    host,
                    dst_filepath,
                    cpus,
                    self._start_timestamp,
                    self._end_timestamp,
                )
            )
        return results

    @classmethod
    def report_results(
        cls,
        recipe: BaseRecipe,
        aggregated_results: list[AggregatedLinuxPerfMeasurementResults],
    ):
        for aggregated_result in aggregated_results:
            cpus: str = ",".join(map(str, aggregated_result.individual_results[0].cpus))
            hostid: str = aggregated_result.individual_results[0].host.hostid
            files: str = "\n    ".join(
                result.filename for result in aggregated_result.individual_results
            )

            recipe.add_result(
                ResultType.PASS,
                f"perf-record recorded CPU(s) {cpus} on {hostid} to files:\n    {files}",
            )

    @classmethod
    def aggregate_results(
        cls,
        old: Optional[list[AggregatedLinuxPerfMeasurementResults]],
        new: list[LinuxPerfMeasurementResults],
    ) -> list[AggregatedLinuxPerfMeasurementResults]:
        if old is None:
            return [AggregatedLinuxPerfMeasurementResults(result) for result in new]

        aggregated: list[AggregatedLinuxPerfMeasurementResults] = []
        for old_measurements, new_measurement in zip(old, new):
            old_measurements.add_results(new_measurement)
            aggregated.append(old_measurements)
        return aggregated
