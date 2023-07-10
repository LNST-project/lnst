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
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import BaseFlowMeasurement


class XDPBenchMeasurement(BaseFlowMeasurement):
    def __init__(self, flows: list[Flow], xdp_command: str, recipe_conf=None):
        super().__init__(recipe_conf)
        self._flows = flows
        self._running_measurements = []
        self._finished_measurements = []

        self.command = xdp_command

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

    def _prepare_server(self, flow: Flow):
        params = {
            "command": self.command,
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

    def collect_results(self):
        test_flows = self._finished_measurements

        results = []
        for test_flow in test_flows:
            flow_results = XDPBenchMeasurementResults(
                measurement=self,
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
    def _report_flow_results(cls, recipe, flow_results):
        generator = flow_results.generator_results
        receiver = flow_results.receiver_results

        desc = []
        desc.extend(flow_results.describe())

        recipe_result = ResultType.PASS
        metrics = {"Generator": generator, "Receiver": receiver}
        for name, result in metrics.items():
            if cls._invalid_flow_duration(result):
                recipe_result = ResultType.FAIL
                desc.append("{} has invalid duration!".format(name))

        recipe.add_result(
            recipe_result,
            "\n".join(desc),
            data=dict(
                generator_flow_data=generator,
                receiver_flow_data=receiver,
                flow_results=flow_results,
            ),
        )
