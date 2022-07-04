from typing import List

from lnst.Controller.Recipe import BaseRecipe
from lnst.Controller.RecipeResults import ResultType
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
            result = ResultType.PASS
            result_text = [
                "Nonzero evaluation of flow:",
                f"{flow_results.flow}"
            ]
            for metric_name in self._metrics_to_evaluate:
                metric = getattr(flow_results, metric_name, None)
                if metric:
                    if metric.average == float("inf"):
                        result = ResultType.FAIL
                        result_text.append(f"{metric_name} reported invalid value: {metric.average}")
                    elif metric.average > 0:
                        report_text = f"{metric_name} reported non-zero throughput"
                        for interval in metric:
                            if interval.value == 0:
                                result = ResultType.FAIL
                                report_text = f"{metric_name} reported zero throughput"
                                break

                        result_text.append(report_text)
                    else:
                        result = ResultType.FAIL
                        result_text.append(f"{metric_name} reported zero throughput")

            recipe.add_result(result, "\n".join(result_text))
