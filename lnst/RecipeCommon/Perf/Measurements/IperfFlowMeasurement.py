import re
import time

from lnst.Common.IpAddress import ipaddress

from lnst.Controller.Recipe import RecipeError
from lnst.Controller.RecipeResults import ResultLevel

from lnst.RecipeCommon.Perf.Results import PerfInterval
from lnst.RecipeCommon.Perf.Results import SequentialPerfResult
from lnst.RecipeCommon.Perf.Results import ParallelPerfResult
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import NetworkFlowTest
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import BaseFlowMeasurement
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import FlowMeasurementResults

from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError

from lnst.Tests.Iperf import IperfClient, IperfServer

class IperfFlowMeasurement(BaseFlowMeasurement):
    _MEASUREMENT_VERSION = 1

    def __init__(self, *args):
        super(IperfFlowMeasurement, self).__init__(*args)
        self._running_measurements = []
        self._finished_measurements = []

        self._hosts_versions = {}

    @property
    def version(self):
        if not self._hosts_versions:
            for flow in self._conf:
                if flow.receiver not in self._hosts_versions:
                    self._hosts_versions[flow.receiver] = self._get_host_iperf_version(flow.receiver)
                if flow.generator not in self._hosts_versions:
                    self._hosts_versions[flow.generator] = self._get_host_iperf_version(flow.generator)

        return {"measurement_version": self._MEASUREMENT_VERSION,
                "hosts_iperf_versions": self._hosts_versions}

    def _get_host_iperf_version(self, host):
        version_job = host.run("iperf3 --version", job_level=ResultLevel.DEBUG)
        if version_job.passed:
            match = re.match(r"iperf (.+?) .*", version_job.stdout)
            if match:
                return match.group(1)
        return None

    def start(self):
        if len(self._running_measurements) > 0:
            raise MeasurementError("Measurement already running!")

        test_flows = self._prepare_test_flows(self._conf)

        result = None
        for flow in test_flows:
            flow.server_job.start(bg=True)

        for flow in test_flows:
            flow.client_job.start(bg=True)

        self._running_measurements = test_flows

    def finish(self):
        test_flows = self._running_measurements
        try:
            for flow in test_flows:
                client_iperf = flow.client_job.what
                flow.client_job.wait(timeout=client_iperf.runtime_estimate())
                flow.server_job.wait(timeout=5)
        finally:
            for flow in test_flows:
                flow.server_job.kill()
                flow.client_job.kill()

        self._running_measurements = []
        self._finished_measurements = test_flows

    def collect_results(self):
        test_flows = self._finished_measurements

        results = []
        for test_flow in test_flows:
            flow_results = FlowMeasurementResults(
                    measurement=self,
                    flow=test_flow.flow)
            flow_results.generator_results = self._parse_job_streams(
                    test_flow.client_job)
            flow_results.generator_cpu_stats = self._parse_job_cpu(
                    test_flow.client_job)

            flow_results.receiver_results = self._parse_job_streams(
                    test_flow.server_job)
            flow_results.receiver_cpu_stats = self._parse_job_cpu(
                    test_flow.server_job)

            results.append(flow_results)

        return results

    def _prepare_test_flows(self, flows):
        test_flows = []
        for flow in flows:
            server_job = self._prepare_server(flow)
            client_job = self._prepare_client(flow)
            test_flow = NetworkFlowTest(flow, server_job, client_job)
            test_flows.append(test_flow)
        return test_flows

    def _prepare_server(self, flow):
        host = flow.receiver
        server_params = dict(bind = ipaddress(flow.receiver_bind),
                             oneoff = True)

        if flow.cpupin is not None and flow.cpupin >= 0:
            if flow.parallel_streams == 1:
                server_params["cpu_bind"] = flow.cpupin
            else:
                raise RecipeError("Unsupported combination of single cpupin "
                                  "with parallel perf streams.")
        elif flow.cpupin is not None:
            raise RecipeError("Negative perf cpupin value provided.")

        return host.prepare_job(IperfServer(**server_params),
                                job_level=ResultLevel.NORMAL)

    def _prepare_client(self, flow):
        host = flow.generator
        client_params = dict(server = ipaddress(flow.receiver_bind),
                             duration = flow.duration)

        if flow.type == "tcp_stream":
            #tcp stream is the default for iperf3
            pass
        elif flow.type == "udp_stream":
            client_params["udp"] = True
        elif flow.type == "sctp_stream":
            client_params["sctp"] = True
        else:
            raise RecipeError("Unsupported flow type '{}'".format(flow.type))

        if flow.cpupin is not None and flow.cpupin >= 0:
            if flow.parallel_streams == 1:
                client_params["cpu_bind"] = flow.cpupin
            else:
                raise RecipeError("Unsupported combination of single cpupin "
                                  "with parallel perf streams.")
        elif flow.cpupin is not None:
            raise RecipeError("Negative perf cpupin value provided.")

        if flow.parallel_streams > 1:
            client_params["parallel"] = flow.parallel_streams

        if flow.msg_size:
            client_params["blksize"] = flow.msg_size

        return host.prepare_job(IperfClient(**client_params),
                                job_level=ResultLevel.NORMAL)

    def _parse_job_streams(self, job):
        result = ParallelPerfResult()
        if not job.passed:
            result.append(PerfInterval(0, 0, "bits"))
        else:
            for i in job.result["data"]["end"]["streams"]:
                result.append(SequentialPerfResult())

            for interval in job.result["data"]["intervals"]:
                for i, stream in enumerate(interval["streams"]):
                    result[i].append(PerfInterval(stream["bytes"] * 8,
                                                  stream["seconds"],
                                                  "bits"))
        return result

    def _parse_job_cpu(self, job):
        if not job.passed:
            return PerfInterval(0, 0, "cpu_percent")
        else:
            cpu_percent = job.result["data"]["end"]["cpu_utilization_percent"]["host_total"]
            return PerfInterval(cpu_percent, 1, "cpu_percent")
