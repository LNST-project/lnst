from .SimpleNetworkRecipe import SimpleNetworkRecipe
from .ConfigMixins.NftablesConntrackMixin import NftablesConntrackMixin

from lnst.Common.Parameters import ConstParam
from lnst.RecipeCommon.Perf.Evaluators import NonzeroFlowEvaluator


class CTInsertionRateNftablesRecipe(NftablesConntrackMixin, SimpleNetworkRecipe):
    net_perf_tool = ConstParam("neper")
    perf_tests = ConstParam(["tcp_crr"])
    perf_msg_sizes = ConstParam([1])

    @property
    def net_perf_evaluators(self):
        return [
            NonzeroFlowEvaluator(["generator_results"])
        ]  # only generator measures CCs, receiver always reports 0

