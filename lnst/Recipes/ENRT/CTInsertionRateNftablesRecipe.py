from .SimpleNetworkRecipe import SimpleNetworkRecipe
from .ConfigMixins.NftablesConntrackMixin import NftablesConntrackMixin

from lnst.Common.Parameters import ConstParam
from lnst.RecipeCommon.Perf.Evaluators import NonzeroFlowEvaluator


class CTInsertionRateNftablesRecipe(NftablesConntrackMixin, SimpleNetworkRecipe):
    """
    The recipe measures insertion rate of conntrack entries on receiver side.
    This is done by using tcp_crr test which opens connections (that trigger 
    adding a new conntrack entry), sends request, waits for response and closes
    the socket. Thats done in a sequence, so we indirectly measure performance
    of conntrack table.

    It's important to keep perf_msg_sizes as small as possible, as transferring
    any amount of data take some time and tcp_crr works in a sequence, so data
    transfer blocks the process of opening new connections and affects the
    results.
    """
    net_perf_tool = ConstParam("neper")
    perf_tests = ConstParam(["tcp_crr"])
    perf_msg_sizes = ConstParam([1])

    @property
    def net_perf_evaluators(self):
        return [
            NonzeroFlowEvaluator(["generator_results"])
        ]  # only generator measures CCs, receiver always reports 0

