from typing import List

from lnst.Controller.Recipe import BaseRecipe

from lnst.RecipeCommon.Perf.Recipe import RecipeConf as PerfRecipeConf
from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import (
    BaseMeasurementResults as PerfMeasurementResults,
)
from lnst.RecipeCommon.BaseResultEvaluator import BaseResultEvaluator


class NonzeroFlowEvaluator(BaseResultEvaluator):
    def evaluate_results(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        results: List[PerfMeasurementResults],
    ):
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
