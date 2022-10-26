from __future__ import division
from typing import List

from lnst.Controller.Recipe import BaseRecipe
from lnst.Controller.RecipeResults import ResultType

from lnst.RecipeCommon.Perf.Recipe import RecipeConf as PerfRecipeConf
from lnst.RecipeCommon.Perf.Results import result_averages_difference
from lnst.RecipeCommon.Perf.Results import SequentialPerfResult
from lnst.RecipeCommon.Perf.Measurements.Results import (
    BaseMeasurementResults as PerfMeasurementResults,
)
from lnst.RecipeCommon.Perf.Evaluators.BaselineEvaluator import (
    BaselineEvaluator, MetricComparison
)


class BaselineFlowAverageEvaluator(BaselineEvaluator):
    def __init__(
        self, thresholds: dict, metrics_to_evaluate: List[str] = None
    ):
        self._thresholds = thresholds

        if metrics_to_evaluate is not None:
            self._metrics_to_evaluate = metrics_to_evaluate
        else:
            self._metrics_to_evaluate = [
                "generator_results",
                "generator_cpu_stats",
                "receiver_results",
                "receiver_cpu_stats",
            ]

    def describe_group_results(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        results: List[PerfMeasurementResults],
    ) -> List[str]:
        result = results[0]
        return [
            "Baseline average evaluation of flow:",
            "{}".format(result.flow)
        ]

    def compare_result_with_baseline(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        result: PerfMeasurementResults,
        baseline: PerfMeasurementResults,
        result_index: int = 0,
    ) -> List[MetricComparison]:
        metric_comparisons = []
        for i in self._metrics_to_evaluate:
            metric = f"{result_index}_{i}"
            if baseline is None:
                comparison_result = ResultType.FAIL
                text = f"FAIL: Metric {metric} baseline not found for this flow"
            elif (threshold := self._thresholds.get(metric, None)) is not None:
                comparison_result, text = self._average_diff_comparison(
                    name=metric,
                    target=getattr(result, i),
                    baseline=getattr(baseline, i),
                    threshold=threshold
                )
            else:
                comparison_result = ResultType.FAIL
                text = f"FAIL: Metric {metric} threshold not found"

            metric_comparisons.append(
                MetricComparison(
                    metric_name=metric,
                    result=comparison_result,
                    text=text,
                )
            )
        return metric_comparisons

    def _average_diff_comparison(
        self,
        name: str,
        target: SequentialPerfResult,
        baseline: SequentialPerfResult,
        threshold: int
    ):
        difference = result_averages_difference(target, baseline)
        result_text = "New {name} average is {diff:.2f}% {direction} from the baseline. " \
                      "Allowed difference: {threshold}%".format(
            name=name,
            diff=abs(difference),
            direction="higher" if difference >= 0 else "lower",
            threshold=threshold
        )

        cpu = "_cpu_" in name

        #  (           flow metrics           ) or (          cpu metrics          )
        if (not cpu and difference > threshold) or (cpu and difference < -threshold):
            comparison = ResultType.WARNING
        elif (not cpu and difference >= -threshold) or (cpu and difference <= threshold):
            comparison = ResultType.PASS
        else:
            comparison = ResultType.FAIL

        if comparison == ResultType.WARNING:
            result_text = f"IMPROVEMENT: {result_text}"
        else:
            result_text = f"{comparison}: {result_text}"

        return comparison, result_text
