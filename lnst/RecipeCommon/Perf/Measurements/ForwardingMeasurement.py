"""
Module implementing the actual Forwarding Measurement.

Copyright 2025 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
sdobron@redhat.com (Samuel Dobron)
"""

from typing import Literal

from lnst.Tests.XDPBench import XDPBench
from lnst.RecipeCommon.Perf.Results import (
    PerfInterval,
    ParallelPerfResult,
    SequentialPerfResult,
)
from lnst.Devices.VlanDevice import VlanDevice
from lnst.Controller.RecipeResults import ResultType
from lnst.Tests.PktGen import PktgenController, PktgenDevice

from lnst.Tests.InterfaceStatsMonitor import InterfaceStatsMonitor
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import (
    Flow,
    NetworkFlowTest,
)
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import BaseFlowMeasurement
from lnst.RecipeCommon.Perf.Measurements.Results.ForwardingMeasurementResults import (
    ForwardingMeasurementResults,
)

from lnst.RecipeCommon.Perf.Measurements.Results.AggregatedForwardingMeasurementResults import (
    AggregatedForwardingMeasurementResults,
)
from lnst.Controller.RecipeResults import MeasurementResult


class ForwardingMeasurement(BaseFlowMeasurement):
    """
    This class implements the forwarding measurement.
    It uses pktgen to generate packets originating from
    :attr:`Flow.generator_nic` destinating :attr:`Flow.receiver_nic`
    via :attr:`Flow.forwarder_nic`.

    :attr:`Flow.receiver_nic` runs XDP-bench in drop mode.
    Sure, we could use some nftables rule but xdp-bench is much
    faster and requires less separate CPUs for dropping packets
    and so, we can use more CPUs for generating traffic.

    This class expect forwarding to be already configured.
    Underlying forwarding plane could be anything like regular
    kernel, xdp-forward, ...

    This measurement runs single instance of pktgen, multiple
    instances of xdp-bench as well as multiple instances of
    interface stats monitor, based on destination/forwarding
    interfaces.

    Since it's not possible to measure individual flows, there
    are just per-interface stats monitors. Results are then
    spread over the flows passing through that interface.
    """

    def __init__(
        self,
        flows,
        ratep=-1,
        burst=1,
        xdp_mode: Literal["skb", "native"] = "native",
        recipe_conf=None,
    ):
        super().__init__(recipe_conf=recipe_conf)
        self._flows = flows
        self._mode = xdp_mode
        self._ratep = ratep
        self._burst = burst

        self._client_job = None  # pktgen
        self._server_job = None  # xdp-bench
        self._forwarder_job = None  # interface stats monitor

        self._finished_client_job = None
        self._finished_server_job = None
        self._finished_forwarder_job = None

        self._net_flows = []

    @property
    def flows(self):
        return self._flows

    def start(self):
        self._prepare_jobs()

        self._server_job.start(bg=True)
        self._forwarder_job.start(bg=True)
        self._client_job.start(bg=True)

    def _prepare_forwarder(self):
        """
        Prepares InterfaceStatsMonitor job at the forwarder.

        There is no other way of measuring forwarded packets
        and as long as :attr:`Flow.forwarder_nic` is used
        for forwarding only. In that case, the numbers are
        correct.
        """
        if not all(
            flow.forwarder_nic == self.flows[0].forwarder_nic for flow in self.flows
        ):
            raise MeasurementError("All flows must have the same forwarder_nic")

        sample_flow = self.flows[0]  # all flows have the same forwarder_nic
        forwarder_nic = self._real_dev(sample_flow.forwarder_nic)

        monitor = InterfaceStatsMonitor(
            device=forwarder_nic,
            duration=sample_flow.duration + sample_flow.warmup_duration * 2,
            stats=["rx_packets"],  # forwarder_nic is forwarder's ingress inf
        )
        job = sample_flow.forwarder_nic.netns.prepare_job(monitor)

        return job

    def _prepare_server(self):
        """
        Prepares xdp-bench in drop mode at the receiver.

        This is an easy way of counting and dropping packets
        afterwards. Any other solution would involve kernel
        which just slow things down...
        """
        if not all(
            flow.receiver_nic == self.flows[0].receiver_nic for flow in self.flows
        ):
            raise MeasurementError("All flows must have the same receiver_nic")

        sample_flow = self.flows[0]  # all flows have the same receiver_nic
        receiver_nic = self._real_dev(sample_flow.receiver_nic)

        params = {
            "command": "drop",
            "xdp_mode": self._mode,
            "interface": receiver_nic,
            "duration": sample_flow.duration + sample_flow.warmup_duration * 2,
        }
        bench = XDPBench(**params)
        job = sample_flow.receiver.prepare_job(bench)

        return job

    def _prepare_client(self):
        if not all(
            flow.generator == self.flows[0].generator for flow in self.flows
        ):
            raise MeasurementError("Multiple generators are not supported")

        config = []
        for flow in self.flows:
            config.append(
                {
                    "src_if": self._real_dev(flow.generator_nic),
                    "dst_mac": flow.forwarder_nic.hwaddr,
                    "src_ip": flow.generator_bind,
                    "dst_ip": flow.receiver_bind,
                    "cpu": flow.generator_cpupin[
                        0
                    ],  # FwdMeasGen round-robins cpus, so this will be list with 1 cpu only
                    "pkt_size": flow.msg_size,
                    "duration": flow.duration + flow.warmup_duration * 2,
                    "src_port": flow.generator_port,
                    "dst_port": flow.receiver_port,
                    "ratep": int(self._ratep / self._burst),  # TODO:
                    # ^ ratep should be set, to prevent bandwidth starvation
                    "burst": self._burst,
                }
            )

        pktgen = PktgenController(config=config)

        job = self.flows[0].generator.prepare_job(pktgen)

        return job

    def _prepare_jobs(self) -> list[NetworkFlowTest]:
        self._client_job = self._prepare_client()
        self._forwarder_job = self._prepare_forwarder()
        self._server_job = self._prepare_server()

        for flow in self.flows:

            net_flow = NetworkFlowTest(flow, self._server_job, self._client_job)
            net_flow.forwarder_job = self._forwarder_job

            self._net_flows.append(net_flow)

    def finish(self):
        try:
            self._client_job.wait(timeout=self._client_job.what.runtime_estimate())
            self._forwarder_job.wait(
                timeout=self._forwarder_job.what.runtime_estimate()
            )
            self._server_job.wait(timeout=self._server_job.what.runtime_estimate())
        finally:
            self._client_job.kill()
            self._forwarder_job.kill()
            self._server_job.kill()

        self._finished_client_job = self._client_job
        self._finished_server_job = self._server_job
        self._finished_forwarder_job = self._forwarder_job

        self._client_job = None
        self._server_job = None
        self._forwarder_job = None

    def collect_results(self):
        results = []

        receiver_results = self._parse_receiver_results()

        forwarder_results = self._parse_forwarder_results()

        generator_results = self._parse_generator_results()

        for net_flow in self._net_flows:
            flow = net_flow.flow
            result = ForwardingMeasurementResults(
                measurement=self,
                measurement_success=True,
                flow=flow,
                warmup_duration=flow.warmup_duration,
            )
            result.generator_results = generator_results[
                PktgenDevice.name_template(self._real_dev(flow.generator_nic), flow.generator_cpupin[0])
            ]
            result.receiver_results = self._spread_results(
                receiver_results,
            )
            result.forwarder_results = self._spread_results(
                forwarder_results,
            )

            results.append(result)

        return results

    def _real_dev(self, device):
        if isinstance(device, VlanDevice):
            return device.realdev
        # TODO: support for other soft devices

        return device

    def _parse_receiver_results(self):
        """
        xdp-bench results parser
        """
        result = (
            ParallelPerfResult()
        )  # multiple instances of xdp-bench container
        results = SequentialPerfResult()  # single instance of xdp-bench

        for sample in self._finished_server_job.result:
            results.append(
                PerfInterval(
                    sample["rx"], sample["duration"], "packets", sample["timestamp"]
                )
            )

        result.append(results)

        return result

    def _parse_generator_results(self) -> dict[str, ParallelPerfResult]:
        """
        pktgen results parser
        """
        nic_results = {}

        for nic, raw_results in self._finished_client_job.result.items():
            results = ParallelPerfResult()  # multiple instances of pktgen
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
            nic_results[nic] = results

        return nic_results

    def _parse_forwarder_results(self):
        result = ParallelPerfResult()
        results = SequentialPerfResult()
        results.extend(
            self.parse_forwarder_samples(
                self._finished_forwarder_job.result, "rx_packets", "packets"
            )
        )

        result.append(results)

        return result

    def _spread_results(self, device_results: SequentialPerfResult) -> ParallelPerfResult:
        """
        Since we cannot measure data for individual flows,
        we need to measure per-interface stats and then spread
        the results over the flows passing through that interface.
        (which is in this case all the flows, as it doesn't support
        multiple paths of flows)

        :param device_results: results from the pktgen device (instance)
        """
        results = ParallelPerfResult()
        spread_results = SequentialPerfResult()

        flows_to_device = len(self.flows)
        for sample in device_results[0]:  # device results are SeqPerfRes
            # ^ iterating over individual samples
            spread_results.append(
                PerfInterval(
                    sample.value / flows_to_device,
                    sample.duration,
                    sample.unit,
                    sample.start_timestamp,
                )
            )
        results.append(spread_results)

        return results

    def parse_forwarder_samples(
        self, raw_samples: list[dict], metric: str, unit: str
    ) -> SequentialPerfResult:
        """
        Parse forwarder results from the interface stats monitor.
        """
        result = SequentialPerfResult()
        previous_timestamp = 0
        previous_value = None

        for raw_sample in raw_samples:
            if not previous_timestamp:
                previous_timestamp = raw_sample["timestamp"]
                previous_value = raw_sample[metric]
                continue

            sample = PerfInterval(
                raw_sample[metric] - previous_value,
                raw_sample["timestamp"] - previous_timestamp,
                unit,
                raw_sample["timestamp"],
            )
            result.append(sample)

            previous_timestamp = raw_sample["timestamp"]
            previous_value = raw_sample[metric]
        return result

    def _aggregate_flows(self, old_flow, new_flow):
        if old_flow is not None and old_flow.flow is not new_flow.flow:
            return MeasurementError("Aggregating different flows")

        new_result = AggregatedForwardingMeasurementResults(
            measurement=self, flow=new_flow.flow
        )
        new_result.add_results(old_flow)
        new_result.add_results(new_flow)

        return new_result

    @classmethod
    def _report_flow_results(cls, recipe, result):
        generator = result.generator_results
        receiver = result.receiver_results
        forwarder = result.forwarder_results

        desc = []
        desc.append(result.describe())

        recipe_result = ResultType.PASS
        metrics = {
            "Generator": generator,
            "Receiver": receiver,
            "Forwarder": forwarder,
        }
        for name, metric_result in metrics.items():
            if cls._invalid_flow_duration(metric_result):
                recipe_result = ResultType.FAIL
                desc.append("{} has invalid duration!".format(name))

        recipe_result = MeasurementResult(
            "forwarding",
            result=(ResultType.PASS if result.measurement_success else ResultType.FAIL),
            description="\n".join(desc),
            data={
                "generator_results": generator,
                "receiver_results": receiver,
                "forwarder_results": forwarder,
            },
        )
        recipe.add_custom_result(recipe_result)

    @staticmethod
    def aggregate_multi_flow_results(results):
        """
        Aggregates results from multiple parallel flows
        into single result.
        """
        if len(results) == 1:
            return results

        sample_result = results[0]
        sample_flow = sample_result.flow
        dummy_flow = Flow(
            type=sample_flow.type,
            generator=sample_flow.generator,
            generator_bind=sample_flow.generator_bind,
            generator_nic=sample_flow.generator_nic,
            receiver=sample_flow.receiver,
            receiver_bind=None,
            receiver_nic=sample_flow.receiver_nic,
            receiver_port=None,
            msg_size=sample_flow.msg_size,
            duration=sample_flow.duration,
            parallel_streams=sample_flow.parallel_streams,
            generator_cpupin=None,
            receiver_cpupin=None,
            aggregated_flow=True,
            warmup_duration=sample_flow.warmup_duration,
        )

        aggregated_result = AggregatedForwardingMeasurementResults(
            sample_result.measurement, dummy_flow
        )

        nr_iterations = len(sample_result.individual_results)
        for i in range(nr_iterations):
            parallel_result = ForwardingMeasurementResults(
                measurement=sample_result.measurement,
                measurement_success=all(
                    result.measurement_success for result in results
                ),
                flow=dummy_flow,
                warmup_duration=dummy_flow.warmup_duration,
            )
            parallel_result.generator_results = ParallelPerfResult()
            parallel_result.forwarder_results = ParallelPerfResult()
            parallel_result.receiver_results = ParallelPerfResult()

            for result in results:
                flow_result = result.individual_results[i]
                parallel_result.generator_results.append(flow_result.generator_results)
                parallel_result.forwarder_results.append(flow_result.forwarder_results)
                parallel_result.receiver_results.append(flow_result.receiver_results)

            aggregated_result.add_results(parallel_result)

        return [aggregated_result]
