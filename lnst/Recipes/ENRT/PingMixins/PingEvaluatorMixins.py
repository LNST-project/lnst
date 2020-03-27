from lnst.RecipeCommon.Ping.Evaluators import (
    ZeroPassPingEvaluator, RatePingEvaluator)

class PingEvaluatorMixin(object):
    def generate_ping_evaluators(self, ping_config, endpoints):
        pass

class VlanPingEvaluatorMixin(PingEvaluatorMixin):
    def generate_ping_evaluators(self, ping_config, endpoints):
        if endpoints.reachable:
            return [RatePingEvaluator(min_rate=50)]
        else:
            return [ZeroPassPingEvaluator()]
