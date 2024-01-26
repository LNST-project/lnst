from lnst.RecipeCommon.Ping.Evaluators import (
    ZeroPassPingEvaluator, RatePingEvaluator)
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpointPair
from lnst.RecipeCommon.Ping.Recipe import PingConf

class PingEvaluatorMixin(object):
    def generate_ping_evaluators(self, ping_config: PingConf, endpoint_pair: PingEndpointPair):
        pass

class VlanPingEvaluatorMixin(PingEvaluatorMixin):
    def generate_ping_evaluators(self, ping_config: PingConf, endpoint_pair: PingEndpointPair):
        if endpoint_pair.should_be_reachable:
            return [RatePingEvaluator(min_rate=50)]
        else:
            return [ZeroPassPingEvaluator()]
