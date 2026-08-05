from lnst.Common.Parameters import IntParam, ListParam, StrParam
from lnst.Recipes.ENRT.MeasurementGenerators.BaseFlowMeasurementGenerator import (
    BaseFlowMeasurementGenerator,
)
from lnst.RecipeCommon.Perf.Measurements.XDPRedirectCPUMeasurement import (
    XDPRedirectCPUMeasurement,
)


class XDPRedirectCPUMeasurementGenerator(BaseFlowMeasurementGenerator):
    """
    Measurement generator mixin for XDP redirect-cpu recipes.

    :param perf_tool_cpu: target CPU IDs on the receiver host for cpumap
        redirect (mandatory). Also used to pin pktgen threads on the generator
        host (round-robin). The IRQ CPU must not appear in this list.
    :type perf_tool_cpu: :any:`ListParam`

    :param ratep: pktgen rate limit in pkt/s, -1 for unlimited (default -1)
    :type ratep: :any:`IntParam`

    :param burst: pktgen burst size (default 1)
    :type burst: :any:`IntParam`

    :param backlog_size: cpumap queue depth per CPU, passed as ``-q`` to
        xdp-bench (default 512)
    :type backlog_size: :any:`IntParam`

    :param xdp_redirect_program: XDP program variant, passed as ``-p`` to
        xdp-bench. Supported: ``l4-dport`` (default), ``l4-sport``.
    :type xdp_redirect_program: :any:`StrParam`

    :param xdp_redirect_remote_action: action after cpumap, passed as ``-r``
        to xdp-bench (default ``drop``)
    :type xdp_redirect_remote_action: :any:`StrParam`
    """

    perf_tool_cpu = ListParam(mandatory=True)
    ratep = IntParam(default=-1)
    burst = IntParam(default=1)
    backlog_size = IntParam(default=512)
    xdp_redirect_program = StrParam(default="l4-dport")
    xdp_redirect_remote_action = StrParam(default="drop")

    @property
    def net_perf_tool_class(self):
        """
        Partial application - same pattern as :class:`XDPFlowMeasurementGenerator`.
        Needed to inject extra params into XDPRedirectCPUMeasurement since
        BaseFlowMeasurementGenerator calls net_perf_tool_class with a fixed
        signature. See https://github.com/LNST-project/lnst/pull/310#discussion_r1305763175
        """

        def _factory(*args, **kwargs):
            return XDPRedirectCPUMeasurement(
                *args,
                cpus=self.params.perf_tool_cpu,
                xdp_program=self.params.xdp_redirect_program,
                xdp_remote_action=self.params.xdp_redirect_remote_action,
                backlog_size=self.params.backlog_size,
                ratep=self.params.ratep,
                burst=self.params.burst,
                **kwargs,
            )

        return _factory

    def generator_cpupin(self, flow_id: int) -> list[int]:
        return self._cpupin_based_on_policy(
            flow_id, self.params.perf_tool_cpu, "round-robin"
        )
