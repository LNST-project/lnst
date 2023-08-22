from typing import Any, Optional, Iterable
from datetime import datetime
import logging
import signal
import time
import os
import re

from lnst.Tests.LinuxPerf import LinuxPerf
from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import BaseMeasurement
from lnst.RecipeCommon.Perf.Measurements.Results import (
    BaseMeasurementResults,
    LinuxPerfMeasurementResults,
    AggregatedLinuxPerfMeasurementResults
)

from lnst.Controller.Job import Job
from lnst.Controller.Host import Host
from lnst.Controller.Recipe import BaseRecipe
from lnst.Controller.RecipeResults import MeasurementResult, ResultLevel


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H:%M:%S")


class LinuxPerfMeasurement(BaseMeasurement):
    _MEASUREMENT_VERSION: int = 1

    linuxperf_cpus: dict[Host, list[list[int]]]
    _start_timestamp: float
    _end_timestamp: float
    _data_folder: str

    _version: Optional[dict[str, Any]] = None
    _collection_index: int = 0
    _running_jobs: list[Job] = []
    _finished_jobs: list[Job] = []

    def __init__(
        self,
        linuxperf_cpus: dict[Host, list[list[int]]],
        data_folder: str,
        recipe_conf: Any = None,
    ):
        super().__init__(recipe_conf)

        self.linuxperf_cpus = linuxperf_cpus
        self._data_folder = data_folder

        # create output folders
        for host in self.hosts:
            try:
                os.mkdir(os.path.join(self._data_folder, host.hostid))
            except FileExistsError:
                pass

    @property
    def hosts(self) -> list[Host]:
        return list(self.linuxperf_cpus.keys())

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
    def configurations(self) -> Iterable[tuple[Host, int, list[int]]]:
        for host in self.hosts:
            for cpu_list_id, cpu_list in enumerate(self.linuxperf_cpus[host]):
                yield (host, cpu_list_id, cpu_list)

    def start(self) -> None:
        self._start_timestamp = time.time()
        for host, cpu_list_id, cpus in self.configurations:
            filename: str = f"cpu_list{cpu_list_id}.cpus.{'.'.join(map(str, cpus))}.data"
            self._running_jobs.append(host.run(LinuxPerf(output_file=filename, cpus=cpus), bg=True))

    def finish(self) -> None:
        for job in self._running_jobs:
            job.kill(signal=signal.SIGINT)

        for job, (host, _, _) in zip(self._running_jobs, self.configurations):
            if not job.wait(timeout=120):
                logging.error(f"timeout while waiting for linuxperf job to finish on host {host.hostid}")
                job.kill()

        self._end_timestamp = time.time()
        self._finished_jobs = self._running_jobs
        self._running_jobs = []

    def collect_results(self) -> list[BaseMeasurementResults]:
        self._collection_index += 1
        results: list[BaseMeasurementResults] = []
        for job, (host, _, cpus) in zip(self._finished_jobs, self.configurations):
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

            recipe.add_custom_result(
                MeasurementResult(
                    "linuxperf",
                    description=f"perf-record recorded CPU(s) {cpus} on {hostid} to files:\n    {files}",
                )
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
