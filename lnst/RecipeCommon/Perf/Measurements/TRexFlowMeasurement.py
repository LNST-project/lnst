import time
import signal
from lnst.Controller.Recipe import RecipeError
from lnst.Controller.RecipeResults import ResultLevel

from lnst.RecipeCommon.Perf.Results import PerfInterval
from lnst.RecipeCommon.Perf.Results import SequentialPerfResult
from lnst.RecipeCommon.Perf.Results import ParallelPerfResult

from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import BaseFlowMeasurement
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import NetworkFlowTest
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import FlowMeasurementResults

from lnst.Tests.TRex import TRexServer, TRexClient

class TRexFlowMeasurement(BaseFlowMeasurement):
    def __init__(self, flows, trex_dir):
        self._flows = flows
        self._trex_dir = trex_dir
        self._running_measurements = []
        self._finished_measurements = []

    def start(self):
        if len(self._running_measurements) > 0:
            raise MeasurementError("Measurement already running!")

        tests = self._prepare_tests(self._flows)

        result = None
        for test in tests:
            test.server_job.start(bg=True)

        for test in tests:
            test.client_job.start(bg=True)

        self._running_measurements = tests

    def finish(self):
        tests = self._running_measurements
        try:
            for test in tests:
                client_test = test.client_job.what
                test.client_job.wait(timeout=client_test.runtime_estimate())

                test.server_job.kill(signal.SIGINT)
                test.server_job.wait(5)
        finally:
            for test in tests:
                test.server_job.kill()
                test.client_job.kill()

        self._running_measurements = []
        self._finished_measurements = tests

    def _prepare_tests(self, flows):
        tests = []

        flows_by_generator = self._flows_by_generator(flows)
        for generator, flows in flows_by_generator.items():
            flow_tuples = [(flow.generator_bind, flow.receiver_bind)
                           for flow in flows]
            server_job = generator.prepare_job(
                    TRexServer(
                        trex_dir=self._trex_dir,
                        flows=flow_tuples,
                        cores=["2", "3", "4"]))
            client_job = generator.prepare_job(
                    TRexClient(
                        trex_dir=self._trex_dir,
                        ports=range(len(flow_tuples)),
                        flows=flow_tuples,
                        duration=flows[0].duration,
                        msg_size=flows[0].msg_size))

            test = NetworkFlowTest(flows, server_job, client_job)
            tests.append(test)
        return tests

    def collect_results(self):
        tests = self._finished_measurements

        results = []
        for test in tests:
            for port, flow in enumerate(test.flow):
                flow_results = self._parse_results_by_port(
                        test.client_job, port, flow)
                results.append(flow_results)

        return results

    def _flows_by_generator(self, flows):
        result = dict()
        for flow in flows:
            if flow.generator in result:
                result[flow.generator].append(flow)
            else:
                result[flow.generator] = [flow]

        for generator, flows in result.items():
            for flow in flows:
                if (flow.duration != flows[0].duration or
                    flow.msg_size != flows[0].msg_size):
                    raise MeasurementError("Flows on the same generator need to have the same duration and msg_size at the moment")
        return result

    def _parse_results_by_port(self, job, port, flow):
        results = FlowMeasurementResults(flow)
        results.generator_results = SequentialPerfResult()
        results.generator_cpu_stats = SequentialPerfResult()

        results.receiver_results = SequentialPerfResult()
        results.receiver_cpu_stats = SequentialPerfResult()

        if not job.passed:
            results.generator_results.append(PerfInterval(0, 0, "packets"))
            results.generator_cpu.append(PerfInterval(0, 0, "cpu_percent"))
            results.receiver_results.append(PerfInterval(0, 0, "packets"))
            results.receiver_cpu.append(PerfInterval(0, 0, "cpu_percent"))
        else:
            prev_time = job.result["start_time"]
            prev_tx_val = 0
            prev_rx_val = 0
            for i in job.result["data"]:
                time_delta = i["timestamp"] - prev_time
                tx_delta = i["measurement"][port]["opackets"] - prev_tx_val
                rx_delta = i["measurement"][port]["ipackets"] - prev_rx_val
                results.generator_results.append(PerfInterval(
                            tx_delta,
                            time_delta,
                            "pkts"))
                results.receiver_results.append(PerfInterval(
                            rx_delta,
                            time_delta,
                            "pkts"))

                prev_time = i["timestamp"]
                prev_tx_val = i["measurement"][port]["opackets"]
                prev_rx_val = i["measurement"][port]["ipackets"]

                cpu_delta = i["measurement"]["global"]["cpu_util"]
                results.generator_cpu_stats.append(PerfInterval(
                    cpu_delta,
                    time_delta,
                    "cpu_percent"))
                results.receiver_cpu_stats.append(PerfInterval(
                    cpu_delta,
                    time_delta,
                    "cpu_percent"))
        return results
