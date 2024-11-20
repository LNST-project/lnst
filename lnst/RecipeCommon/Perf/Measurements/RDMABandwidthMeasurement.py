from typing import Any, Optional
import time
import logging

from lnst.Controller.Job import Job
from lnst.Controller.Recipe import BaseRecipe
from lnst.Controller.RecipeResults import MeasurementResult
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import Flow, NetworkFlowTest
from lnst.RecipeCommon.Perf.Results import PerfInterval
from lnst.Tests.RDMABandwidth import RDMABandwidthServer, RDMABandwidthClient
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import BaseFlowMeasurement
from lnst.RecipeCommon.Perf.Measurements.Results import (
    RDMABandwidthMeasurementResults,
    AggregatedRDMABandwidthMeasurementResults
)


class RDMABandwidthMeasurement(BaseFlowMeasurement):
    def __init__(
        self,
        flows: list[Flow],
        recipe_conf: Any = None,
    ):
        super().__init__(recipe_conf)

        self._flows = flows
        self._endpoint_tests: list[NetworkFlowTest] = []

    @property
    def flows(self) -> list[Flow]:
        return self._flows

    def start(self) -> None:
        self._endpoint_tests.extend(self._prepare_endpoint_tests())

        for endpoint_test in self._endpoint_tests:
            endpoint_test.server_job.start(bg=True)

        time.sleep(2)

        self._start_timestamp = time.time()
        for endpoint_test in self._endpoint_tests:
            endpoint_test.client_job.start(bg=True)

    def simulate_start(self):
        self._endpoint_tests.extend(self._prepare_endpoint_tests())

        for endpoint_test in self._endpoint_tests:
            endpoint_test.server_job = endpoint_test.server_job.netns.run("echo simulated start", bg=True)

        self._start_timestamp = time.time()
        for endpoint_test in self._endpoint_tests:
            endpoint_test.client_job = endpoint_test.client_job.netns.run("echo simulated start", bg=True)

    def finish(self) -> None:
        try:
            for endpoint_test in self._endpoint_tests:
                timeout = endpoint_test.flow.duration + 5
                endpoint_test.client_job.wait(timeout=timeout)
                endpoint_test.server_job.wait(timeout=timeout)
        finally:
            for endpoint_test in self._endpoint_tests:
                endpoint_test.client_job.kill()
                endpoint_test.server_job.kill()

    def simulate_finish(self):
        logging.info("Simulating minimal 1s measurement duration")
        time.sleep(1)
        self.finish()

    def collect_results(self) -> list[RDMABandwidthMeasurementResults]:
        results: list[RDMABandwidthMeasurementResults] = []
        for endpoint_test in self._endpoint_tests:
            bandwidth = endpoint_test.client_job.result["bandwidth"]
            duration = endpoint_test.flow.duration
            result = RDMABandwidthMeasurementResults(
                measurement=self,
                measurement_success=(
                    endpoint_test.client_job.passed and endpoint_test.server_job.passed
                ),
                flow=endpoint_test.flow,
            )
            result.bandwidth = PerfInterval(
                # pre-multiply to get the total amount of bytes sent
                value=bandwidth * duration,
                duration=duration,
                unit="MiB",
                timestamp=self._start_timestamp,
            )
            results.append(result)
        self._endpoint_tests.clear()
        return results

    def _prepare_endpoint_tests(self) -> list[NetworkFlowTest]:
        return [
            NetworkFlowTest(
                flow=flow,
                server_job=self._prepare_server_job(flow),
                client_job=self._prepare_client_job(flow),
            )
            for flow in self.flows
        ]

    def _prepare_server_job(self, flow: Flow) -> Job:
        params = {
            "device_name": self.recipe_conf.rdma_device_name,
            "duration": flow.duration,
            "port": flow.receiver_port,
            "size": flow.msg_size,
        }
        if flow.receiver_cpupin is not None:
            params["cpu_bind"] = flow.receiver_cpupin

        return flow.receiver.prepare_job(RDMABandwidthServer(**params))

    def _prepare_client_job(self, flow: Flow) -> Job:
        params = {
            "device_name": self.recipe_conf.rdma_device_name,
            "dst_ip": flow.receiver_bind,
            "src_ip": flow.generator_bind,
            "duration": flow.duration,
            "port": flow.receiver_port,
            "size": flow.msg_size,
        }
        if flow.generator_cpupin is not None:
            params["cpu_bind"] = flow.generator_cpupin

        if flow.warmup_duration > 0:
            params["perform_warmup"] = True

        return flow.generator.prepare_job(RDMABandwidthClient(**params))

    @classmethod
    def aggregate_results(
        cls,
        old: Optional[list[AggregatedRDMABandwidthMeasurementResults]],
        new: list[RDMABandwidthMeasurementResults],
    ) -> list[AggregatedRDMABandwidthMeasurementResults]:
        if old is None:
            agg_results = []
            for result in new:
                agg_result = AggregatedRDMABandwidthMeasurementResults(result.measurement, result.flow)
                agg_result.add_results(result)
                agg_results.append(agg_result)
            return agg_results

        aggregated: list[AggregatedRDMABandwidthMeasurementResults] = []
        for old_measurements, new_measurement in zip(old, new):
            old_measurements.add_results(new_measurement)
            aggregated.append(old_measurements)
        return aggregated

    @classmethod
    def report_results(
        cls,
        recipe: BaseRecipe,
        aggregated_results: list[AggregatedRDMABandwidthMeasurementResults],
    ) -> None:
        for aggregated_result in aggregated_results:
            measurement_result = MeasurementResult(
                "rdma-bandwidth",
                description=aggregated_result.describe(),
                data={"bandwidth": aggregated_result.bandwidth}
            )
            recipe.add_custom_result(measurement_result)
