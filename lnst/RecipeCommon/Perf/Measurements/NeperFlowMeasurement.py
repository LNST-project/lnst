import time
import logging
from typing import List, Dict, Tuple
from lnst.Common.IpAddress import ipaddress
from lnst.Controller.Job import Job
from lnst.Common.Utils import pairwise
from lnst.Controller.Recipe import RecipeError
from lnst.Controller.RecipeResults import ResultLevel
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import BaseFlowMeasurement, NetworkFlowTest, Flow
from lnst.RecipeCommon.Perf.Measurements.Results.NeperFlowMeasurementResults import NeperFlowMeasurementResults
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError
from lnst.RecipeCommon.Perf.Results import PerfInterval, SequentialPerfResult, ParallelPerfResult
from lnst.Tests.Neper import NeperServer, NeperClient


class NeperFlowMeasurement(BaseFlowMeasurement):
    _MEASUREMENT_VERSION = 1

    def __init__(self, flows: List[Flow], recipe_conf=None):
        super(NeperFlowMeasurement, self).__init__(recipe_conf)
        self._flows = flows
        self._running_measurements = []
        self._finished_measurements = []
        self._host_versions = {}

    @property
    def flows(self) -> List[Flow]:
        return self._flows

    @property
    def version(self):
        return {"measurement_version": self._MEASUREMENT_VERSION,
                "hosts_neper_versions": self._host_versions}

    def start(self):
        if len(self._running_measurements) > 0:
            raise MeasurementError("Measurement already running!")

        test_flows = self._prepare_test_flows(self.flows)

        for flow in test_flows:
            flow.server_job.start(bg=True)

        for flow in test_flows:
            flow.client_job.start(bg=True)

        self._running_measurements = test_flows

    def simulate_start(self):
        if len(self._running_measurements) > 0:
            raise MeasurementError("Measurement already running!")

        test_flows = self._prepare_test_flows(self.flows)

        result = None
        for flow in test_flows:
            flow.server_job = flow.server_job.netns.run('echo simulated start', bg=True)

        for flow in test_flows:
            flow.client_job = flow.client_job.netns.run('echo simulated start', bg=True)

        self._running_measurements = test_flows

    def finish(self):
        test_flows = self._running_measurements
        try:
            for flow in test_flows:
                client_neper = flow.client_job.what
                flow.client_job.wait(timeout=client_neper.runtime_estimate())
                flow.server_job.wait(timeout=10)
        finally:
            for flow in test_flows:
                flow.server_job.kill()
                flow.client_job.kill()

        self._running_measurements = []
        self._finished_measurements = test_flows

    def simulate_finish(self):
        logging.info("Simulating minimal 1s measurement duration")
        time.sleep(1)
        test_flows = self._running_measurements
        for flow in test_flows:
            flow.client_job.wait()
            flow.server_job.wait()

        self._running_measurements = []
        self._finished_measurements = test_flows

    def _prepare_test_flows(self, flows: List[Flow]):
        test_flows = []
        for flow in flows:
            server_job = self._prepare_server(flow)
            client_job = self._prepare_client(flow)
            test_flow = NetworkFlowTest(flow, server_job, client_job)
            test_flows.append(test_flow)
        return test_flows

    def _prepare_server(self, flow: Flow) -> Job:
        host = flow.receiver
        server_params = dict(workload = flow.type,
                             bind = ipaddress(flow.receiver_bind),
                             test_length = flow.duration,
                             warmup_duration = flow.warmup_duration)

        self._set_cpupin_params(server_params, flow.receiver_cpupin)

        if flow.msg_size:
            server_params["request_size"] = flow.msg_size
            server_params["response_size"] = flow.msg_size

        return host.prepare_job(NeperServer(**server_params),
                                job_level=ResultLevel.NORMAL)

    def _prepare_client(self, flow: Flow) -> Job:
        host = flow.generator
        client_params = dict(workload = flow.type,
                             server = ipaddress(flow.receiver_bind),
                             test_length = flow.duration,
                             warmup_duration = flow.warmup_duration)

        self._set_cpupin_params(client_params, flow.generator_cpupin)

        #TODO Figure out what to do about parallel_streams
        # (num_treads? num_flows? possible 2 instances runing at once?)
        # Added NeperBase options to configure num_threads, num_flows but
        # it appears parallel streams is not needed for now.
        # The legacy lnst doesnt seem to use the paralellism even when
        # setting perf_parallel_steams
        #if flow.parallel_streams > 1:
            # client_params["parallel"] = flow.parallel_streams

        if flow.msg_size:
            client_params["request_size"] = flow.msg_size
            client_params["response_size"] = flow.msg_size

        return host.prepare_job(NeperClient(**client_params),
                                job_level=ResultLevel.NORMAL)

    def _set_cpupin_params(self, params, cpupin):
        if cpupin is not None:
            for cpu in cpupin:
                if cpu < 0:
                    raise RecipeError("Negative perf cpupin value provided.")

            # at the moment iperf does not support pinning to multiple cpus
            # so pin to the first cpu specified in the list
            if len(cpupin) > 1:
                raise RecipeError("Cannot pin neper to the specified list "\
                    "of cpus due to use not supporting it with neper.")

            params["cpu_bind"] = cpupin[0]

    def collect_results(self) -> List[NeperFlowMeasurementResults]:
        test_flows = self._finished_measurements

        results = []
        for test_flow in test_flows:
            flow_results = NeperFlowMeasurementResults(
                    measurement=self,
                    measurement_success=(
                        test_flow.client_job.passed and test_flow.server_job.passed
                    ),
                    flow=test_flow.flow,
                    warmup_duration=test_flow.flow.warmup_duration
            )
            generator_stats = self._parse_job_samples(test_flow.client_job)
            flow_results.generator_results = generator_stats[0]
            flow_results.generator_cpu_stats = generator_stats[1]
            self._host_versions[test_flow.flow.generator] = \
                test_flow.client_job.result["data"]["VERSION"]

            receiver_stats = self._parse_job_samples(test_flow.server_job)
            flow_results.receiver_results = receiver_stats[0]
            flow_results.receiver_cpu_stats = receiver_stats[1]
            self._host_versions[test_flow.flow.receiver] = \
                test_flow.server_job.result["data"]["VERSION"]

            results.append(flow_results)

        return results

    def _parse_job_samples(self, job: Job) ->\
            Tuple[ParallelPerfResult, ParallelPerfResult]:
        """
        each perfinterval is samples.csv line #2 (l2) - line #1 (l1) to get # transactions and duration
        timestamp is time of l1, but we need to convert it from CLOCK_MONOTONIC time to unix time.
        samples.csv looks like this:
        ```
        tid,flow_id,time,transactions,utime,stime,maxrss,minflt,majflt,nvcsw,nivcsw,latency_min,latency_mean,latency_max,latency_stddev
        0,0,1898645.747723502,1,0.000371,0.000000,1144,39,0,2,0,0.000000,0.000000,0.000000,-nan
        0,0,1898647.747733162,59322,0.185458,0.241758,1144,43,0,59320,0,0.000000,0.000000,0.000000,0.000000
        0,0,1898648.747757407,89210,0.281500,0.354934,1144,43,0,89207,0,0.000000,0.000000,0.000000,0.000000
        0,0,1898649.747737156,118790,0.281500,0.354934,1144,43,0,89207,0,0.000000,0.000000,0.000000,0.000000
        ```
        :param job:
        :type job:
        :return:
        :rtype:
        """

        results = SequentialPerfResult()
        cpu_results = SequentialPerfResult()

        if not job.passed:
            results.append(PerfInterval(0, 1, "transactions", time.time()))
            cpu_results.append(PerfInterval(0, 1, "cpu_percent", time.time()))
        elif job.what.is_crr_server():
            # Neper doesn't support server stats for tcp_crr due to memory issues.
            # Use perf_interval of 0.
            # For duration neper doesn't have time_start/time_end for tcp_crr
            # So just use the value of test length
            d = float(job.what.params.test_length)
            results.append(PerfInterval(0, d, "transactions", time.time()))
            cpu_results.append(PerfInterval(0, d, "cpu_percent", time.time()))
        else:
            job_start = job.result['start_time']
            samples = job.result['samples']
            if samples is not None:
                neper_start_time = float(samples[0]['time'])
                for s_start, s_end in pairwise(samples):
                    flow, cpu = get_interval(s_start, s_end,
                                             job_start, neper_start_time)
                    results.append(flow)
                    cpu_results.append(cpu)

        #Wrap in ParallelPerfResult for now for easier graphing
        #TODO When we add support for multiple flows and threads
        #We want to update this accordingly.
        p_results = ParallelPerfResult()
        p_results.append(results)
        p_cpu_results = ParallelPerfResult()
        p_cpu_results.append(cpu_results)
        return p_results, p_cpu_results


def get_interval(s_start: Dict, s_end: Dict, job_start: float,
                 neper_start: float) -> Tuple[PerfInterval, PerfInterval]:

    transactions = int(s_end['transactions']) - int(s_start['transactions'])
    s_start_time = float(s_start['time'])
    s_start_utime = float(s_start['utime'])
    s_start_stime = float(s_start['stime'])

    s_end_time = float(s_end['time'])
    s_end_utime = float(s_end['utime'])
    s_end_stime = float(s_end['stime'])

    # cpu_usage_percent = (utime_delta + stime_delta) / duration
    utime_delta = s_end_utime - s_start_utime
    stime_delta = s_end_stime - s_start_stime

    # neper uses CLOCK_MONOTONIC, need to convert to
    # unix time using job_start as reference
    timestamp = job_start + (s_start_time - neper_start)
    duration = s_end_time - s_start_time
    cpu_usage = ((utime_delta + stime_delta) / duration) * 100

    interval = PerfInterval(transactions, duration, 'transactions', timestamp)
    cpu_interval = PerfInterval(cpu_usage * duration, duration, 'cpu_percent', timestamp)

    return interval, cpu_interval
