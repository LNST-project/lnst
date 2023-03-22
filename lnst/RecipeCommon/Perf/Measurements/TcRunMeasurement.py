import logging
from os import PathLike
from tempfile import NamedTemporaryFile
from typing import Optional

from lnst.Common.NetUtils import MacPool
from lnst.Controller import BaseRecipe
from lnst.Controller.RecipeResults import ResultLevel, ResultType
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError
from lnst.RecipeCommon.Perf.Measurements.Results.AggregatedTcRunMeasurementResults import AggregatedTcRunMeasurementResults
from lnst.RecipeCommon.Perf.Measurements.Results.TcRunMeasurementResults import TcRunMeasurementResults
from lnst.RecipeCommon.Perf.Results import PerfInterval
from lnst.Tests.TrafficControl import TrafficControlRunner
from lnst.Controller.Job import Job
from lnst.Controller.Namespace import Device, Namespace
from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import BaseMeasurement


class TcRunInstance:
    MAX_ID = 0xFFFF

    def __init__(self, device: Device, num_rules: int, instance_id:int):
        self._device = device
        self._num_rules = num_rules
        self._instance_id = instance_id
        self._batchfile_path: PathLike = None
        self._instance_job: Job = None
        self.validate()

    @property
    def instance_job(self):
        return self._instance_job

    @instance_job.setter
    def instance_job(self, job: Job):
        self._instance_job = job

    @property
    def batchfile_path(self):
        return self._batchfile_path

    @batchfile_path.setter
    def batchfile_path(self, p: PathLike):
        self._batchfile_path = p

    def validate(self):
        if self._instance_id > self.MAX_ID:
            raise ValueError(f"Maximum number of instances supported is {self.MAX_ID}")
        try:
            required_macs = self._num_rules * 2 # Each rule needs src/dest mac
            required_macs.to_bytes(3,'big')
        except OverflowError:
            raise ValueError(f"Can't create enough MAC addresses for {self._num_rules}")

    @property
    def num_rules(self) -> int:
        return self._num_rules

    @property
    def pool_oui(self) -> str:
        # Somewhat simple way to create a mac pool of unicast address
        return f"00:{self._instance_id.to_bytes(2, 'big').hex(':')}"

    @property
    def device(self) -> Device:
        return self._device

    @property
    def host(self) -> Namespace:
        return self._device.host

    @property
    def start_mac(self) -> str:
        return f"{self.pool_oui}:00:00:00"

    @property
    def end_mac(self) -> str:
        return f"{self.pool_oui}:ff:ff:ff"

    def generate_batchfile(self) -> str:
        logging.info(f"Generating tc batchfile for {self.device.name} instance {self._instance_id} num_rules={self.num_rules}")
        rules = self.generate_rules()
        with NamedTemporaryFile(
                'w', suffix=".batch", prefix="tc-rules-", delete=True,
        ) as f:
            for r in rules:
                f.write(r)

            remote_path = self.host.copy_file_to_machine(f.name)
        self.batchfile_path = remote_path
        logging.info(f"tc batchfile written to {self.host.hostname}:{remote_path}")
        return remote_path

    def generate_rules(self):
        mac_pool = MacPool(self.start_mac, self.end_mac)
        iface = self.device.name

        for i in range(self.num_rules):
            a = i & 0xff
            b = (i & 0xff00) >> 8
            c = (i & 0xff0000) >> 16
            src_mac = mac_pool.get_addr()
            dst_mac = mac_pool.get_addr()
            yield f"filter add dev {iface} parent ffff: protocol ip prio 1 flower " \
                  f"src_mac {src_mac} dst_mac {dst_mac} " \
                  f"src_ip 56.{a}.{b}.{c} dst_ip 55.{c}.{b}.{a} action drop\n"


class TcRunMeasurement(BaseMeasurement):

    def __init__(
            self,
            device: Device,
            num_instances: int,
            rules_per_instance: int,
            timeout: int = 120,
            parent_recipe_conf=None,
    ):
        super().__init__(recipe_conf=parent_recipe_conf)
        self._device = device
        self._num_instances = num_instances
        self._rules_per_instance = rules_per_instance
        self._running_jobs: list[Job] = []
        self._finished_jobs: dict[Job] = []
        self._timeout = timeout
        self.instance_configs = self._make_instances_cfgs()

    @property
    def num_instances(self):
        return self._num_instances

    @property
    def version(self):
        # TODO Need to figure out how best to
        # categorize tc version, `tc -V` gives:
        # tc utility, iproute2-5.18.0, libbpf 0.6.0

        return 1

    @property
    def device(self):
        return self._device

    @property
    def host(self):
        return self._device.host

    def start(self):
        if len(self._running_jobs) > 0:
            raise MeasurementError("Measurement already running!")

        jobs = self._prepare_jobs()
        for job in jobs:
            job.start(bg=True)
            self._running_jobs.append(job)

    def _prepare_jobs(self) -> list[Job]:
        jobs = []
        for instance in self.instance_configs:
            batchfile = instance.generate_batchfile()
            job = instance.host.prepare_job(
                TrafficControlRunner(batchfile=batchfile),
                job_level=ResultLevel.NORMAL,
            )
            instance.instance_job = job
            jobs.append(job)
        return jobs

    def finish(self):
        jobs = self._running_jobs
        try:
            for job in jobs:
                job.wait(self._timeout)
        finally:
            for job in jobs:
                job.kill()
        self._running_jobs = []
        self._finished_jobs = jobs

    def _make_instances_cfgs(self) -> list[TcRunInstance]:
        #TODO perhaps make this be something the recipe or a ResultGenerator creates
        configs = []
        for i in range(self._num_instances):
            cfg = TcRunInstance(
                device=self.device,
                num_rules=self._rules_per_instance,
                instance_id=i,
            )
            configs.append(cfg)
        return configs

    def collect_results(self) -> list[TcRunMeasurementResults]:
        results: list[TcRunMeasurementResults] = []
        for job in self._finished_jobs:
            run_result = TcRunMeasurementResults(
                measurement=self,
                device=self.device,
            )
            run_result.rule_install_rate = PerfInterval(
                value=self._rules_per_instance,
                duration=job.result['data']['time_taken'],
                unit='rules',
                timestamp=job.result['data']['start_timestamp'],
            )
            run_result.run_success = job.passed
            results.append(run_result)

        return results

    @classmethod
    def report_results(cls, recipe: BaseRecipe, results: list[TcRunMeasurementResults]):
        for result in results:
            cls._report_result(recipe, result)

    @classmethod
    def _report_result(cls,  recipe: BaseRecipe, result: TcRunMeasurementResults):
        r_type = ResultType.PASS if result.run_success else ResultType.FAIL
        recipe.add_result(
            r_type,
            f"{r_type} {result.description}",
            data=dict(
                rule_install_rate=result.rule_install_rate,
            )
        )

    @classmethod
    def aggregate_results(cls, old: Optional[list[TcRunMeasurementResults]], new: list[TcRunMeasurementResults]):
        aggregated = []
        if old is None:
            old = [None] * len(new)
        for old_measurements, new_measurements in zip(old, new):
            aggregated.append(cls.aggregate_run_results(
                old_measurements, new_measurements))
        return aggregated

    @classmethod
    def aggregate_run_results(cls, old: Optional[TcRunMeasurementResults], new: TcRunMeasurementResults):
        if old is not None and (old.device is not new.device):
            raise MeasurementError("Aggregating incompatible Device Results")

        new_result = AggregatedTcRunMeasurementResults(
            measurement=new.measurement,
            device=new.device,
        )
        new_result.add_results(old)
        new_result.add_results(new)
        return new_result

    @classmethod
    def aggregate_parallel_run_results(cls, results: list[TcRunMeasurementResults]):
        if len(results) <= 1:
            return results

        aggregated_result = AggregatedTcRunMeasurementResults(
            measurement=results[0].measurement,
            device=results[0].device
        )

        for result in results:
            aggregated_result.add_results(result)

        return [aggregated_result]
