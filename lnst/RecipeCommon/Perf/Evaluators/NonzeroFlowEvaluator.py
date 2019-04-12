from lnst.RecipeCommon.Perf.Evaluators.BaseEvaluator import BaseEvaluator

from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import (
    FlowMeasurementResults,
    AggregatedFlowMeasurementResults,
)


class NonzeroFlowEvaluator(BaseEvaluator):
    def evaluate_results(self, recipe, results):
        for flow_results in results:
            result = True
            result_text = ["Flow {} Nonzero evaluation".format(flow_results.flow)]
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
