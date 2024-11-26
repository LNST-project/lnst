import time
import logging

from lnst.Controller.Recipe import BaseRecipe
from lnst.RecipeCommon.Perf.Measurements.Results.AggregatedXDPBenchMeasurementResults import (
    AggregatedXDPBenchMeasurementResults,
)
from lnst.Controller.RecipeResults import ResultType
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import (
    Flow,
    NetworkFlowTest,
)
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError
from lnst.RecipeCommon.Perf.Measurements.Results.XDPBenchMeasurementResults import (
    XDPBenchMeasurementResults,
)
from lnst.RecipeCommon.Perf.Results import (
    PerfInterval,
    ParallelPerfResult,
    SequentialPerfResult,
)
from lnst.Tests.PktGen import PktGen
from lnst.Tests.XDPBench import XDPBench
from lnst.Controller.Job import Job
from lnst.Controller.RecipeResults import MeasurementResult, ResultType
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import BaseFlowMeasurement


class XDPBenchMeasurement(BaseFlowMeasurement):
    def __init__(
        self,
        flows: list[Flow],
        xdp_command: str,
        xdp_mode: str,
        xdp_load_mode: str = None,
        xdp_packet_operation: str = None,
        xdp_remote_action: str = None,
        recipe_conf=None,
    ):
        super().__init__(recipe_conf)
        self._flows = flows
        self._running_measurements = []
        self._finished_measurements = []

        self.command = xdp_command
        self.mode = xdp_mode
        self.load_mode = xdp_load_mode
        self.packet_operation = xdp_packet_operation
        self.remote_action = xdp_remote_action

    def version(self):
        return 1.0

    @property
    def flows(self):
        return self._flows

    def start(self):
        net_flows = self._prepare_flows()
        for flow in net_flows:
            flow.server_job.start(bg=True)
            flow.client_job.start(bg=True)
            # server starts immediately, no need to wait
            self._running_measurements.append(flow)

        self._running_measurements = net_flows

    def simulate_start(self):
        net_flows = self._prepare_flows()
        for flow in net_flows:
            flow.server_job = flow.server_job.netns.run("echo simulated start", bg=True)
            flow.client_job = flow.client_job.netns.run("echo simulated start", bg=True)
            # server starts immediately, no need to wait
            self._running_measurements.append(flow)

        self._running_measurements = net_flows

    def _prepare_server(self, flow: Flow):
        params = {
            "command": self.command,
            "xdp_mode": self.mode,
            "load_mode": self.load_mode,
            "packet_operation": self.packet_operation,
            "remote_action": self.remote_action,
            "interface": flow.receiver_nic,
            "duration": flow.duration + flow.warmup_duration * 2,
        }
        bench = XDPBench(**params)
        job = flow.receiver.prepare_job(bench)

        return job

    def _prepare_client(self, flow: Flow):
        params = {
            "src_if": flow.generator_nic,
            "dst_mac": flow.receiver_nic.hwaddr,
            "src_ip": flow.generator_bind,
            "dst_ip": flow.receiver_bind,
            "cpus": flow.generator_cpupin,
            "pkt_size": flow.msg_size,
            "duration": flow.duration + flow.warmup_duration * 2,
        }
        pktgen = PktGen(**params)

        job = flow.generator.prepare_job(pktgen)

        return job

    def _prepare_flows(self) -> list[NetworkFlowTest]:
        flows = []
        for flow in self.flows:
            client = self._prepare_client(flow)
            server = self._prepare_server(flow)
            net_flow = NetworkFlowTest(flow, server, client)
            flows.append(net_flow)

        return flows

    def finish(self):
        try:
            for flow in self._running_measurements:
                client_job = flow.client_job.what
                flow.client_job.wait(timeout=client_job.runtime_estimate())
                flow.server_job.wait(timeout=5)
        finally:
            for flow in self._running_measurements:
                flow.server_job.kill()
                flow.client_job.kill()
        self._finished_measurements = self._running_measurements
        self._running_measurements = []

    def simulate_finish(self):
        logging.info("Simulating minimal 1s measurement duration")
        time.sleep(1)
        for flow in self._running_measurements:
            flow.server_job.wait()
            flow.client_job.wait()
        self._finished_measurements = self._running_measurements
        self._running_measurements = []

    def collect_results(self):
        test_flows = self._finished_measurements

        results = []
        for test_flow in test_flows:
            flow_results = XDPBenchMeasurementResults(
                measurement=self,
                measurement_success=(
                    test_flow.client_job.passed and test_flow.server_job.passed
                ),
                flow=test_flow.flow,
                warmup_duration=test_flow.flow.warmup_duration,
            )
            flow_results.generator_results = self._parse_generator_results(
                test_flow.client_job,
            )
            flow_results.receiver_results = self._parse_receiver_results(
                test_flow.server_job
            )

            results.append(flow_results)
        return results

    def _parse_generator_results(self, job: Job):
        results = ParallelPerfResult()  # container for multiple instances of pktgen

        for _, raw_results in job.result.items():
            instance_results = SequentialPerfResult()  # instance (device) of pktgen
            for raw_result in raw_results:
                sample = PerfInterval(
                    raw_result["packets"],
                    raw_result["duration"],
                    "packets",
                    raw_result["timestamp"],
                )
                instance_results.append(sample)
            results.append(instance_results)

        return results

    def _parse_receiver_results(self, job: Job):
        result = (
            ParallelPerfResult()
        )  # just a placeholder to keep data structure same as other Measurements
        results = SequentialPerfResult()  # single instance of xdp-bench

        for sample in job.result:
            results.append(
                PerfInterval(
                    sample["rx"], sample["duration"], "packets", sample["timestamp"]
                )
            )

        result.append(results)

        return result

    def _aggregate_flows(self, old_flow, new_flow):
        if old_flow is not None and old_flow.flow is not new_flow.flow:
            raise MeasurementError("Aggregating incompatible Flows")

        new_result = AggregatedXDPBenchMeasurementResults(
            measurement=self, flow=new_flow.flow
        )

        new_result.add_results(old_flow)
        new_result.add_results(new_flow)
        return new_result

    @classmethod
    def report_results(cls, recipe: BaseRecipe, results: list[AggregatedXDPBenchMeasurementResults]):
        for result in results:
            generator = result.generator_results
            receiver = result.receiver_results

            desc = []
            desc.append(result.describe())

            recipe_result = ResultType.PASS
            metrics = {"Generator": generator, "Receiver": receiver}
            for name, metric_result in metrics.items():
                if cls._invalid_flow_duration(metric_result):
                    recipe_result = ResultType.FAIL
                    desc.append("{} has invalid duration!".format(name))

            recipe_result = MeasurementResult(
                "xdp-bench",
                result=(
                    ResultType.PASS
                    if result.measurement_success
                    else ResultType.FAIL
                ),
                description="\n".join(desc),
                data={
                    "generator_results": generator,
                    "receiver_results": receiver,
                    "flow_results": result,
                },
            )
            recipe.add_custom_result(recipe_result)
