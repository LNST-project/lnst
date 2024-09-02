import time
import signal
import socket
import logging

from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import (
    BaseFlowMeasurement,
    NetworkFlowTest,
    Flow,
)
from lnst.Tests.Latency import LatencyClient, LatencyServer

from lnst.RecipeCommon.Perf.Measurements.Results.LatencyMeasurementResults import (
    LatencyMeasurementResults,
)
from lnst.RecipeCommon.Perf.Measurements.Results.AggregatedLatencyMeasurementResults import (
    AggregatedLatencyMeasurementResults,
)

from lnst.Controller.Job import Job

from lnst.RecipeCommon.Perf.Results import (
    PerfInterval,
    ScalarSample,
    ParallelPerfResult,
    SequentialScalarResult,
)
from lnst.Controller.RecipeResults import ResultType


class LatencyMeasurement(BaseFlowMeasurement):
    def __init__(
        self,
        flows,
        recipe_conf,
        port: int,
        payload_size: int,
        samples_count: int,
        cache_poison_tool: callable = None,
    ):
        super().__init__(recipe_conf)

        self._flows = flows
        self._latency_flows = []

        self._port = port
        self._data_size = payload_size
        self._samples_count = samples_count

        self._cache_poison_tool = cache_poison_tool

    def version(self):
        return "1.0"

    @property
    def data_size(self):
        return self._data_size

    @property
    def samples_count(self):
        return self._samples_count

    @property
    def cache_poison_tool_name(self):
        return self._cache_poison_tool.__name__

    @property
    def flows(self):
        return self._flows

    def start(self):
        logging.info("Starting LatencyMeasurement")

        jobs = self._prepare_jobs()

        for measurements in self._latency_flows:
            measurements.server_job.start(bg=True)
            time.sleep(5)
            measurements.client_job.start(bg=True)

        time.sleep(
            0.1 * self._samples_count
        )  # should be enough for client to gather samples

        if self._cache_poison_tool is not None:
            logging.info("Cache poisoning tool is set, running...")
            self._cache_poison_tool(self.recipe_conf)
        else:
            logging.warning("No cache poisoning tool set, is this intended?")

        return True

    def _prepare_jobs(self):
        for flow in self._flows:
            server = self._prepare_server(flow)
            client = self._prepare_client(flow)

            self._latency_flows.append(NetworkFlowTest(flow, server, client))

    def _prepare_client(self, flow: Flow) -> Job:
        params = {
            "host": flow.receiver_bind,
            "port": self._port,
            "duration": flow.duration,
            "samples_count": self._samples_count,
            "data_size": self._data_size,
        }

        client = LatencyClient(**params)
        return flow.generator.prepare_job(client)

    def _prepare_server(self, flow: Flow) -> Job:
        params = {
            "host": flow.receiver_bind,
            "samples_count": self._samples_count,
            "data_size": self._data_size,
        }

        server = LatencyServer(**params)
        return flow.receiver.prepare_job(server)

    def finish(self):
        for measurements in self._latency_flows:
            measurements.client_job.kill(signal.SIGINT)
            measurements.server_job.kill(signal.SIGINT)

    def collect_results(self) -> list[LatencyMeasurementResults]:
        results = []
        # each list element represents measuremet results for one flow
        # so, most of the time there will be only one element
        # but in case of parallel flows, there will be more

        for measurements in self._latency_flows:
            flow_results = LatencyMeasurementResults(
                measurement=self,
                flow=measurements.flow,
            )

            flow_results.latency = SequentialScalarResult()

            samples = []
            prev_duration = 0
            prev_timestamp, _ = measurements.client_job.result[0]
            for latency, timestamp in measurements.client_job.result:
                samples.append(
                    ScalarSample(latency, "nanoseconds", prev_timestamp + prev_duration)
                )
                prev_duration = latency
                prev_timestamp = timestamp

            flow_results.latency.extend(samples)

            results.append(flow_results)

        return results

    @classmethod
    def _report_flow_results(cls, recipe, flow_results):
        desc = []
        desc.append(flow_results.describe())

        recipe.add_result(
            ResultType.PASS,
            "\n".join(desc),
            data=dict(
                flow_results=flow_results,
            ),
        )

    def _aggregate_flows(self, old_flow, new_flow):
        if old_flow is not None and old_flow.flow is not new_flow.flow:
            raise MeasurementError("Aggregating incompatible Flows")

        new_result = AggregatedLatencyMeasurementResults(
            measurement=self, flow=new_flow.flow
        )

        new_result.add_results(old_flow)
        new_result.add_results(new_flow)
        return new_result

    def __repr__(self):
        return "{}({})".format(
            self.__class__.__name__,
            repr(self.recipe_conf),
        )
