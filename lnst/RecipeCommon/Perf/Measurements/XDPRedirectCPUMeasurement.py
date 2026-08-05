import logging

from lnst.Tests.XDPBenchRedirectCpu import XDPBenchRedirectCpu
from lnst.Tests.PktGen import PktgenController
from lnst.RecipeCommon.Perf.Results import (
    PerfInterval,
    ParallelPerfResult,
    SequentialPerfResult,
)
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import (
    BaseFlowMeasurement,
    NetworkFlowTest,
)
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError
from lnst.RecipeCommon.Perf.Measurements.Results.XDPRedirectCPUMeasurementResults import (
    XDPRedirectCPUMeasurementResults,
)
from lnst.RecipeCommon.Perf.Measurements.Results.AggregatedXDPRedirectCPUMeasurementResults import (
    AggregatedXDPRedirectCPUMeasurementResults,
)
from lnst.Controller.RecipeResults import MeasurementResult, ResultType


class XDPRedirectCPUMeasurement(BaseFlowMeasurement):
    """
    Measurement for ``xdp-bench redirect-cpu``.

    Starts a single ``xdp-bench redirect-cpu`` instance on the receiver with
    all target CPUs as ``-c`` flags, and a multi-flow pktgen instance on the
    generator.

    One aggregated :class:`XDPRedirectCPUMeasurementResults` is returned per
    measurement run, covering all flows.

    :param flows: list of :class:`Flow` objects, one per pktgen instance
    :param cpus: target CPU IDs on the receiver for cpumap redirect
    :param xdp_program: ``-p`` flag for xdp-bench. Supported: ``l4-dport``
        (default) and ``l4-sport``. LNST creates multiple flows distinguished
        by src/dst port, so only port-based programs distribute flows across
        CPUs correctly.
    :param xdp_remote_action: ``-r`` flag for xdp-bench (default ``drop``)
    :param backlog_size: ``-q`` flag, cpumap queue depth per CPU (default 512)
    :param ratep: pktgen rate limit in pkt/s, -1 for unlimited (default -1)
    :param burst: pktgen burst size (default 1)
    """

    def __init__(
        self,
        flows,
        cpus: list[int] = None,
        xdp_program: str = "l4-dport",
        xdp_remote_action: str = "drop",
        backlog_size: int = 512,
        ratep=-1,
        burst=1,
        recipe_conf=None,
    ):
        super().__init__(recipe_conf=recipe_conf)
        _SUPPORTED_PROGRAMS = {"l4-dport", "l4-sport"}
        if xdp_program not in _SUPPORTED_PROGRAMS:
            raise MeasurementError(
                f"xdp_program={xdp_program!r} is not supported. "
                f"Supported: {sorted(_SUPPORTED_PROGRAMS)}. "
                "LNST distinguishes flows by src/dst port; only port-based "
                "programs distribute them across CPUs correctly."
            )
        self._flows = flows
        self._cpus = cpus or []
        self._xdp_program = xdp_program
        self._xdp_remote_action = xdp_remote_action
        self._backlog_size = backlog_size
        self._ratep = ratep
        self._burst = burst

        self._generator_job = None
        self._receiver_job = None
        self._finished_generator_job = None
        self._finished_receiver_job = None
        self._net_flows = []

    @property
    def flows(self):
        return self._flows

    def start(self):
        if not all(
            flow.receiver_nic == self.flows[0].receiver_nic for flow in self.flows
        ):
            raise MeasurementError("All flows must have the same receiver_nic")
        if not all(flow.generator == self.flows[0].generator for flow in self.flows):
            raise MeasurementError("Multiple generators are not supported")
        if not all(flow.duration == self.flows[0].duration for flow in self.flows):
            raise MeasurementError("All flows must have the same duration")
        if not all(
            flow.warmup_duration == self.flows[0].warmup_duration
            for flow in self.flows
        ):
            raise MeasurementError("All flows must have the same warmup duration")

        self._generator_job = self._prepare_client()
        self._receiver_job = self._prepare_receiver()

        for flow in self.flows:
            self._net_flows.append(
                NetworkFlowTest(flow, self._receiver_job, self._generator_job)
            )

        self._receiver_job.start(bg=True)
        self._generator_job.start(bg=True)

    def _prepare_receiver(self):
        sample_flow = self.flows[0]
        bench = XDPBenchRedirectCpu(
            interface=sample_flow.receiver_nic,
            cpus=self._cpus,
            program=self._xdp_program,
            remote_action=self._xdp_remote_action,
            qsize=self._backlog_size,
            duration=sample_flow.duration + sample_flow.warmup_duration * 2,
        )
        return sample_flow.receiver.prepare_job(bench)

    def _prepare_client(self):
        config = []
        for flow in self.flows:
            cpu = flow.generator_cpupin[0] if flow.generator_cpupin else None
            ratep = (
                int(self._ratep / self._burst) if self._ratep >= 0 else self._ratep
            )
            config.append(
                {
                    "src_if": flow.generator_nic,
                    "dst_mac": flow.receiver_nic.hwaddr,
                    "src_ip": flow.generator_bind,
                    "dst_ip": flow.receiver_bind,
                    "cpu": cpu,
                    "pkt_size": flow.msg_size,
                    "duration": flow.duration + flow.warmup_duration * 2,
                    "src_port": flow.generator_port,
                    "dst_port": flow.receiver_port,
                    "ratep": ratep,
                    "burst": self._burst,
                }
            )
        pktgen = PktgenController(config=config)
        return self.flows[0].generator.prepare_job(pktgen)

    def finish(self):
        try:
            self._generator_job.wait(
                timeout=self._generator_job.what.runtime_estimate()
            )
            self._receiver_job.wait(
                timeout=self._receiver_job.what.runtime_estimate()
            )
        finally:
            self._generator_job.kill()
            self._receiver_job.kill()

        self._finished_generator_job = self._generator_job
        self._finished_receiver_job = self._receiver_job
        self._generator_job = None
        self._receiver_job = None

    def collect_results(self):
        generator_results = self._parse_generator_results()
        receiver_results, forwarded_results = self._parse_receiver_results()

        flows = [net_flow.flow for net_flow in self._net_flows]
        warmup_duration = flows[0].warmup_duration if flows else 0

        result = XDPRedirectCPUMeasurementResults(
            measurement=self,
            measurement_success=(
                bool(generator_results)
                and self._finished_receiver_job is not None
                and self._finished_receiver_job.passed
            ),
            flows=flows,
            warmup_duration=warmup_duration,
        )
        result.generator_results = generator_results
        result.receiver_results = receiver_results
        result.forwarded_results = forwarded_results

        self._net_flows = []
        return [result]

    def _parse_generator_results(self) -> ParallelPerfResult:
        if not self._finished_generator_job.passed:
            return ParallelPerfResult()

        results = ParallelPerfResult()
        for _, raw_results in self._finished_generator_job.result.items():
            instance_results = SequentialPerfResult()
            for raw_result in raw_results:
                instance_results.append(
                    PerfInterval(
                        raw_result["packets"],
                        raw_result["duration"],
                        "packets",
                        raw_result["timestamp"],
                    )
                )
            results.append(instance_results)
        return results

    def _parse_receiver_results(self):
        """
        Returns ``(receiver_results, forwarded_results)``:

        - ``receiver_results``: :class:`ParallelPerfResult` with one
          :class:`SequentialPerfResult` per target CPU (kthread cpu:N pkt/s)
        - ``forwarded_results``: :class:`ParallelPerfResult` with a single
          :class:`SequentialPerfResult` (receive total pkt/s, IRQ CPU)
        """
        receiver_results = ParallelPerfResult()
        forwarded_results = ParallelPerfResult()

        if not self._finished_receiver_job or not self._finished_receiver_job.passed:
            return receiver_results, forwarded_results

        for _ in self._cpus:
            receiver_results.append(SequentialPerfResult())

        irq_total = SequentialPerfResult()

        for sample in self._finished_receiver_job.result:
            irq_total.append(
                PerfInterval(
                    sample["received"],
                    sample["duration"],
                    "packets",
                    sample["timestamp"],
                )
            )
            for cpu, pkts in sample["forwarded_per_cpu"].items():
                try:
                    flow_idx = self._map_cpu_to_flow_id(cpu)
                except ValueError:
                    logging.warning(f"Unexpected CPU {cpu} in xdp-bench output, skipping")
                    continue
                receiver_results[flow_idx].append(
                    PerfInterval(
                        pkts,
                        sample["duration"],
                        "packets",
                        sample["timestamp"],
                    )
                )

        forwarded_results.append(irq_total)
        return receiver_results, forwarded_results

    def _map_cpu_to_flow_id(self, cpu: int) -> int:
        return self._cpus.index(cpu)

    def _aggregate_flows(self, old_flow, new_flow):
        if old_flow is None:
            return new_flow

        if isinstance(old_flow, AggregatedXDPRedirectCPUMeasurementResults):
            old_flow.add_results(new_flow)
            return old_flow

        aggregated = AggregatedXDPRedirectCPUMeasurementResults(
            measurement=self, flows=new_flow.flows
        )
        aggregated.add_results(old_flow)
        aggregated.add_results(new_flow)
        return aggregated

    @classmethod
    def report_results(cls, recipe, results):
        for result in results:
            generator = result.generator_results
            receiver = result.receiver_results
            forwarded = result.forwarded_results

            desc = [result.describe()]
            recipe_result = ResultType.PASS

            for name, metric in [
                ("Generator", generator),
                ("Receiver", receiver),
                ("Forwarded", forwarded),
            ]:
                if cls._invalid_flow_duration(metric):
                    recipe_result = ResultType.FAIL
                    desc.append(f"{name} has invalid duration!")

            recipe.add_custom_result(
                MeasurementResult(
                    "xdp-redirect-cpu",
                    result=(
                        ResultType.PASS
                        if result.measurement_success and recipe_result == ResultType.PASS
                        else ResultType.FAIL
                    ),
                    description="\n".join(desc),
                    data={
                        "generator_results": generator,
                        "receiver_results": receiver,
                        "forwarded_results": forwarded,
                    },
                )
            )
