from __future__ import division
from typing import List, Tuple

from lnst.Controller.Recipe import BaseRecipe
from lnst.Controller.RecipeResults import ResultType

from lnst.RecipeCommon.Perf.Recipe import RecipeConf as PerfRecipeConf
from lnst.RecipeCommon.Perf.Results import result_averages_difference
from lnst.RecipeCommon.Perf.Results import SequentialPerfResult
from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import (
    BaseMeasurementResults as PerfMeasurementResults,
)
from lnst.RecipeCommon.Perf.Evaluators.BaselineEvaluator import (
    BaselineEvaluator,
)


class BaselineFlowAverageEvaluator(BaselineEvaluator):
    def __init__(
        self, pass_difference: int, metrics_to_evaluate: List[str] = None
    ):
        self._pass_difference = pass_difference

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
            "{}".format(result.flow),
            "Configured {}% difference as acceptable".format(
                self._pass_difference
            ),
        ]

    def compare_result_with_baseline(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        result: PerfMeasurementResults,
        baseline: PerfMeasurementResults,
    ) -> Tuple[ResultType, List[str]]:
        comparison_result = ResultType.PASS
        result_text = []
        if baseline is None:
            comparison_result = ResultType.FAIL
            result_text.append("No baseline found for this flow")
        else:
            for i in self._metrics_to_evaluate:
                comparison, text = self._average_diff_comparison(
                    name=i,
                    target=getattr(result, i),
                    baseline=getattr(baseline, i),
                )
                result_text.append(text)
                comparison_result = ResultType.max_severity(comparison_result, comparison)
        return comparison_result, result_text

    def _average_diff_comparison(
        self,
        name: str,
        target: SequentialPerfResult,
        baseline: SequentialPerfResult,
    ):
        difference = result_averages_difference(target, baseline)
        result_text = "New {name} average is {diff:.2f}% {direction} from the baseline {name}".format(
            name=name,
            diff=abs(difference),
            direction="higher" if difference >= 0 else "lower",
        )

        cpu = "_cpu_" in name

        #  (                 flow metrics                 ) or (                cpu metrics                )
        if (not cpu and difference > self._pass_difference) or (cpu and difference < -self._pass_difference):
            comparison = ResultType.WARNING
        elif (not cpu and difference >= -self._pass_difference) or (cpu and difference <= self._pass_difference):
            comparison = ResultType.PASS
        else:
            comparison = ResultType.FAIL

        if comparison == ResultType.WARNING:
            result_text = f"IMPROVEMENT: {result_text}"
        else:
            result_text = f"{comparison}: {result_text}"

        return comparison, result_text
