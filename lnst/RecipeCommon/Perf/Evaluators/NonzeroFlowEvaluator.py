from typing import List

from lnst.Controller.Recipe import BaseRecipe

from lnst.RecipeCommon.Perf.Recipe import RecipeConf as PerfRecipeConf
from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import (
    BaseMeasurementResults as PerfMeasurementResults,
)
from lnst.RecipeCommon.BaseResultEvaluator import BaseResultEvaluator


class NonzeroFlowEvaluator(BaseResultEvaluator):
    def __init__(self, metrics_to_evaluate: List[str] = None):
        if metrics_to_evaluate is not None:
            self._metrics_to_evaluate = metrics_to_evaluate
        else:
            self._metrics_to_evaluate = [
                "generator_results",
                "receiver_results",
            ]

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
            for metric_name in self._metrics_to_evaluate:
                metric = getattr(flow_results, metric_name, None)
                if metric:
                    if metric.average == float("inf"):
                        result = False
                        result_text.append(
                            "{} reported invalid value: {}".format(
                                metric_name,
                                metric.average
                            )
                        )
                    elif metric.average > 0:
                        result_text.append(
                            "{} reported non-zero throughput".format(
                                metric_name
                            )
                        )
                    else:
                        result = False
                        result_text.append(
                            "{} reported zero throughput".format(metric_name)
                        )

            recipe.add_result(result, "\n".join(result_text))
