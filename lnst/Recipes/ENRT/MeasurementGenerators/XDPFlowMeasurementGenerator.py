from lnst.Common.Parameters import ChoiceParam, StrParam
from lnst.RecipeCommon.Perf.Measurements.XDPBenchMeasurement import XDPBenchMeasurement
from lnst.Recipes.ENRT.MeasurementGenerators.BaseFlowMeasurementGenerator import (
    BaseFlowMeasurementGenerator,
)

from lnst.Tests.XDPBench import XDP_BENCH_COMMANDS


class XDPFlowMeasurementGenerator(BaseFlowMeasurementGenerator):
    xdp_command = ChoiceParam(type=StrParam, choices=XDP_BENCH_COMMANDS)

    @property
    def net_perf_tool_class(self):
        """
        This method uses the concept of partial application [1].

        BaseFlowMeasurementGenerator.generate_perf_measurement_combinations
        calls net_perf_tool_class and passes some arguments to the returned class.
        However, XDPBenchMeasurement requires additional arguments, so the
        only way to pass them is to either redefine the entire
        generate_perf_measurement_combinations method or return a partially 
        "initialised" class from net_perf_tool_class.

        [1] https://github.com/LNST-project/lnst/pull/310#discussion_r1305763175
        """
        def XDPBenchMeasurement_partial(*args, **kwargs):
            return XDPBenchMeasurement(*args, self.params.xdp_command, **kwargs)

        return XDPBenchMeasurement_partial

