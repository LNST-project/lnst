import time
import logging
from tempfile import NamedTemporaryFile
from typing import Optional

from lnst.Common.NetUtils import MacPool
from lnst.Controller import BaseRecipe
from lnst.Controller.RecipeResults import MeasurementResult, ResultLevel, ResultType
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError
from lnst.RecipeCommon.Perf.Measurements.Results.AggregatedTcRunMeasurementResults import AggregatedTcRunMeasurementResults
from lnst.RecipeCommon.Perf.Measurements.Results.TcRunMeasurementResults import TcRunMeasurementResults
from lnst.RecipeCommon.Perf.Results import PerfInterval, ParallelPerfResult
from lnst.Tests.TrafficControl import TrafficControlRunner
from lnst.Controller.Job import Job
from lnst.Controller.Namespace import Device, Namespace
from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import BaseMeasurement


class TcRunInstance:
    MAX_ID = 0xFFFF

    def __init__(self, device: Device, num_rules: int, instance_id: int, batchfile_path: Optional[str] = None):
        self._device = device
        self._num_rules = num_rules
        self._instance_id = instance_id

        if batchfile_path is None:
            batchfile_path = self._generate_batchfile()
        self._batchfile_path = batchfile_path

        self.validate()

    @property
    def batchfile_path(self):
        return self._batchfile_path

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

    def _generate_batchfile(self) -> str:
        logging.info(f"Generating tc batchfile for {self.device.name} instance {self._instance_id} num_rules={self.num_rules}")
        rules = self.generate_rules()
        with NamedTemporaryFile(
                'w', suffix=".batch", prefix="tc-rules-", delete=True,
        ) as f:
            for r in rules:
                f.write(r)

            remote_path = self.host.copy_file_to_machine(f.name)
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
            cpu_bind: Optional[list[int]] = None,
            cpu_bind_policy: str = "round-robin",
            parent_recipe_conf=None,
    ):
        super().__init__(recipe_conf=parent_recipe_conf)
        self._device = device
        self._num_instances = num_instances
        self._rules_per_instance = rules_per_instance
        self._running_jobs: list[Job] = []
        self._finished_jobs: dict[Job] = []
        self._timeout = timeout
        self._cpu_bind = cpu_bind
        self._cpu_bind_policy = cpu_bind_policy
        self.instance_configs = self._make_instances_cfgs()

    @property
    def num_instances(self):
        return self._num_instances

    @property
    def rules_per_instance(self):
        return self._rules_per_instance

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

    def simulate_start(self):
        if len(self._running_jobs) > 0:
            raise MeasurementError("Measurement already running!")

        jobs = self._prepare_jobs()

        for job in jobs:
            job = job.netns.run("echo simulated start", bg=True)
            self._running_jobs.append(job)

    def _prepare_jobs(self) -> list[Job]:
        params: dict = {
            "batchfiles": [i.batchfile_path for i in self.instance_configs],
        }
        if self._cpu_bind is not None:
            params["cpu_bind"] = self._cpu_bind
            params["cpu_bind_policy"] = self._cpu_bind_policy

        job = self.host.prepare_job(
            TrafficControlRunner(**params),
            job_level=ResultLevel.NORMAL,
        )
        return [job]

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

    def simulate_finish(self):
        logging.info("Simulating minimal 1s measurement duration")
        time.sleep(1)
        self.finish()

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
        run_result = TcRunMeasurementResults(
            measurement=self,
            device=self.device,
        )
        if len(self._finished_jobs) > 1:
            raise MeasurementError("Too many jobs")
        job = self._finished_jobs[0]
        instance_data = job.result["data"]["instance_results"]

        run_result.rule_install_rate = ParallelPerfResult(
            [self._get_instance_interval(d) for d in instance_data]
        )
        run_result.run_success = job.passed

        return [run_result]

    def collect_simulated_results(self):
        run_result = TcRunMeasurementResults(
            measurement=self,
            device=self.device,
        )
        run_result.rule_install_rate = ParallelPerfResult(
            [PerfInterval(0, 1, "rules", time.time())]
        )
        run_result.run_success = True
        return [run_result]

    def _get_instance_interval(self, instance_data: dict):
        return PerfInterval(
            value=self._rules_per_instance,
            duration=instance_data['time_taken'],
            unit='rules',
            timestamp=instance_data['start_timestamp'],
        )

    @classmethod
    def report_results(cls, recipe: BaseRecipe, results: list[TcRunMeasurementResults]):
        for result in results:
            cls._report_result(recipe, result)

    @classmethod
    def _report_result(cls,  recipe: BaseRecipe, result: TcRunMeasurementResults):
        r_type = ResultType.PASS if result.run_success else ResultType.FAIL
        measurement_result = MeasurementResult(
            "tc",
            description=f"{r_type} {result.description}",
            data={"rule_install_rate": result.rule_install_rate},
        )
        recipe.add_custom_result(measurement_result)

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
