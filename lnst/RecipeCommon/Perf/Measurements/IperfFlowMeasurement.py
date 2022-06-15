import re
import time
from typing import List

from lnst.Common.IpAddress import ipaddress

from lnst.Controller.Recipe import RecipeError
from lnst.Controller.RecipeResults import ResultLevel

from lnst.RecipeCommon.Perf.Results import PerfInterval
from lnst.RecipeCommon.Perf.Results import SequentialPerfResult
from lnst.RecipeCommon.Perf.Results import ParallelPerfResult
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import Flow
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import NetworkFlowTest
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import BaseFlowMeasurement
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import FlowMeasurementResults

from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError

from lnst.Tests.Iperf import IperfClient, IperfServer

class IperfFlowMeasurement(BaseFlowMeasurement):
    _MEASUREMENT_VERSION = 1

    def __init__(self, flows: List[Flow], recipe_conf=None):
        super(IperfFlowMeasurement, self).__init__(recipe_conf)
        self._flows = flows
        self._running_measurements = []
        self._finished_measurements = []

        self._hosts_versions = {}

    @property
    def flows(self):
        return self._flows

    @property
    def version(self):
        if not self._hosts_versions:
            for flow in self.flows:
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

        test_flows = self._prepare_test_flows(self.flows)

        result = None
        for flow in test_flows:
            flow.server_job.start(bg=True)

        time.sleep(2)
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
                    flow=test_flow.flow,
                    warmup_duration=test_flow.flow.warmup_duration
            )
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

        self._set_cpupin_params(server_params, flow.cpupin)

        if flow.type == "mptcp_stream":
            server_params["mptcp"] = True

        if flow.receiver_port is not None:
            server_params["port"] = flow.receiver_port

        return host.prepare_job(IperfServer(**server_params),
                                job_level=ResultLevel.NORMAL)

    def _prepare_client(self, flow):
        host = flow.generator
        client_params = {
            "server": ipaddress(flow.receiver_bind),
            "duration": flow.duration,
            "warmup_duration": flow.warmup_duration
        }

        if flow.type == "tcp_stream":
            #tcp stream is the default for iperf3
            pass
        elif flow.type == "udp_stream":
            client_params["udp"] = True
        elif flow.type == "sctp_stream":
            client_params["sctp"] = True
        elif flow.type == "mptcp_stream":
            client_params["mptcp"] = True
        else:
            raise RecipeError("Unsupported flow type '{}'".format(flow.type))

        self._set_cpupin_params(client_params, flow.cpupin)

        if flow.parallel_streams > 1:
            client_params["parallel"] = flow.parallel_streams

        if flow.msg_size:
            client_params["blksize"] = flow.msg_size

        if flow.receiver_port is not None:
            client_params["port"] = flow.receiver_port

        return host.prepare_job(IperfClient(**client_params),
                                job_level=ResultLevel.NORMAL)

    def _set_cpupin_params(self, params, cpupin):
        if cpupin is not None:
            for cpu in cpupin:
                if cpu < 0:
                    raise RecipeError("Negative perf cpupin value provided.")

            # at the moment iperf does not support pinning to multiple cpus
            # so pin to the first cpu specified in the list
            if len(cpupin) > 1:
                raise RecipeError("Cannot pin iperf to the specified list "\
                    "of cpus due to missing support in iperf.")

            params["cpu_bind"] = cpupin[0]

    def _parse_job_streams(self, job):
        result = ParallelPerfResult()
        if not job.passed:
            result.append(PerfInterval(0, 0, "bits", time.time()))
        else:
            for i in job.result["data"]["end"]["streams"]:
                result.append(SequentialPerfResult())

            job_start = job.result["data"]["start"]["timestamp"]["timesecs"]
            for interval in job.result["data"]["intervals"]:
                interval_start = interval["sum"]["start"]
                for i, stream in enumerate(interval["streams"]):
                    result[i].append(PerfInterval(stream["bytes"] * 8,
                                                  stream["seconds"],
                                                  "bits", job_start + interval_start))
        return result

    def _parse_job_cpu(self, job):
        if not job.passed:
            return PerfInterval(0, 0, "cpu_percent", time.time())
        else:
            cpu_percent = job.result["data"]["end"]["cpu_utilization_percent"]["host_total"]
            job_start = job.result["data"]["start"]["timestamp"]["timesecs"]
            duration = job.result["data"]["start"]["test_start"]["duration"]
            return PerfInterval(cpu_percent*duration, duration, "cpu_percent", job_start)
