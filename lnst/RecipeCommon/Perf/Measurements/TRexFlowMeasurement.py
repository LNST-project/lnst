import time
import signal
import re
from lnst.Controller.Recipe import RecipeError
from lnst.Controller.RecipeResults import ResultLevel

from lnst.RecipeCommon.Perf.Results import PerfInterval
from lnst.RecipeCommon.Perf.Results import SequentialPerfResult
from lnst.RecipeCommon.Perf.Results import ParallelPerfResult

from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import BaseFlowMeasurement
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import NetworkFlowTest
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import FlowMeasurementResults

from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError

from lnst.Tests.TRex import TRexServer, TRexClient

class TRexFlowMeasurement(BaseFlowMeasurement):
    _MEASUREMENT_VERSION = 1

    def __init__(self, flows, trex_dir, server_cpu_cores, recipe_conf=None):
        super(TRexFlowMeasurement, self).__init__(
            measurement_conf=dict(
                flows=flows,
                trex_dir=trex_dir,
                server_cpu_cores=server_cpu_cores,
            ),
            recipe_conf=recipe_conf,
        )
        self._flows = flows
        self._trex_dir = trex_dir
        self._server_cpu_cores = server_cpu_cores
        self._conf = dict(flows=flows, trex_dir=trex_dir)
        self._running_measurements = []
        self._finished_measurements = []

        self._hosts_versions = {}

    @property
    def flows(self):
        return self._flows

    @property
    def version(self):
        if not self._hosts_versions:
            for flow in self._flows:
                if flow.generator not in self._hosts_versions:
                    self._hosts_versions[flow.generator] = self._get_host_trex_version(flow.generator)

        return {"measurement_version": self._MEASUREMENT_VERSION,
                "hosts_trex_versions": self._hosts_versions}

    def _get_host_trex_version(self, host):
        version_job = host.run(f"cd {self._trex_dir} ; ./t-rex-64 --help", job_level = ResultLevel.DEBUG)
        if version_job.passed:
            match = re.match(r"Starting  TRex (v.+?) please wait  ...", version_job.stdout)
            if match:
                return match.group(1)
        return None

    def start(self):
        if len(self._running_measurements) > 0:
            raise MeasurementError("Measurement already running!")

        tests = self._prepare_tests(self._flows)

        result = None
        for test in tests:
            test.server_job.start(bg=True)

        #wait for Trex server to start
        time.sleep(15)

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
        for generator, flows in list(flows_by_generator.items()):
            flow_tuples = [(flow.generator_bind, flow.receiver_bind)
                           for flow in flows]
            server_job = generator.prepare_job(
                    TRexServer(
                        trex_dir=self._trex_dir,
                        flows=flow_tuples,
                        cores=self._server_cpu_cores))
            client_job = generator.prepare_job(
                    TRexClient(
                        trex_dir=self._trex_dir,
                        ports=list(range(len(flow_tuples))),
                        flows=flow_tuples,
                        module=flows[0].type,
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

        for generator, flows in list(result.items()):
            for flow in flows:
                if (flow.duration != flows[0].duration or
                    flow.msg_size != flows[0].msg_size):
                    raise MeasurementError("Flows on the same generator need to have the same duration and msg_size at the moment")
        return result

    def _parse_results_by_port(self, job, port, flow):
        results = FlowMeasurementResults(measurement=self, flow=flow)
        results.generator_results = SequentialPerfResult()
        results.generator_cpu_stats = SequentialPerfResult()

        results.receiver_results = SequentialPerfResult()
        results.receiver_cpu_stats = SequentialPerfResult()

        if not job.passed:
            results.generator_results.append(PerfInterval(0, 0, "packets"))
            results.generator_cpu_stats.append(PerfInterval(0, 0, "cpu_percent"))
            results.receiver_results.append(PerfInterval(0, 0, "packets"))
            results.receiver_cpu_stats.append(PerfInterval(0, 0, "cpu_percent"))
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
