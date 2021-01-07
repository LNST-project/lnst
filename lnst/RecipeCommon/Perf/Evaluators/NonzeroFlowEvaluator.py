from lnst.RecipeCommon.BaseResultEvaluator import BaseResultEvaluator

from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import (
    FlowMeasurementResults,
    AggregatedFlowMeasurementResults,
)


class NonzeroFlowEvaluator(BaseResultEvaluator):
    def evaluate_results(self, recipe, recipe_conf, results):
        for flow_results in results:
            result = True
            result_text = [
                "Nonzero evaluation of flow:",
                "{}".format(flow_results.flow),
            ]
            if flow_results.generator_results.average > 0:
                result_text.append("Generator reported non-zero throughput")
            else:
                result = False
                result_text.append("Generator reported zero throughput")

            if flow_results.receiver_results.average > 0:
                result_text.append("Receiver reported non-zero throughput")
            else:
                result = False
                result_text.append("Receiver reported zero throughput")

            recipe.add_result(result, "\n".join(result_text))
