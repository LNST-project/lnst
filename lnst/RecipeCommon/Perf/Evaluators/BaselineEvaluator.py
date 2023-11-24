from typing import List, Optional
from functools import reduce
from dataclasses import dataclass

from lnst.Controller.Recipe import BaseRecipe
from lnst.Controller.RecipeResults import ResultType, Result
from lnst.RecipeCommon.BaseResultEvaluator import BaseResultEvaluator
from lnst.RecipeCommon.Perf.Recipe import RecipeConf as PerfRecipeConf
from lnst.RecipeCommon.Perf.Results import result_averages_difference
from lnst.RecipeCommon.Perf.Measurements.Results import (
    BaseMeasurementResults as PerfMeasurementResults,
)


@dataclass
class MetricComparison:
    measurement_type: str
    current_result: PerfMeasurementResults
    baseline_result: Optional[PerfMeasurementResults]
    threshold: float
    metric_name: str
    difference: float
    comparison_result: ResultType
    text: str


class BaselineEvaluationResult(Result):
    def __init__(
        self, comparisons: list[MetricComparison], recipe_conf: PerfRecipeConf
    ):
        super().__init__(ResultType.PASS)
        self.comparisons = comparisons
        self.recipe_conf = recipe_conf

    @property
    def result(self) -> ResultType:
        return reduce(
            ResultType.max_severity,
            [comparison.comparison_result for comparison in self.comparisons],
            ResultType.PASS,
        )

    @property
    def description(self) -> str:
        res = []
        current_result = None
        for comparison in self.comparisons:
            if comparison.current_result != current_result:
                res.append(comparison.current_result.describe())
                current_result = comparison.current_result
            res.append(f"{comparison.comparison_result}: {comparison.text}")
        return "\n".join(
            ["Baseline evaluation of"] + res
        )


class BaselineEvaluator(BaseResultEvaluator):
    def __init__(self, metrics_to_evaluate: Optional[List[str]] = None):
        self._metrics_to_evaluate = metrics_to_evaluate

    def evaluate_results(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        results: List[PerfMeasurementResults],
    ):
        filtered_results = self.filter_results(recipe, recipe_conf, results)

        for group in self.group_results(recipe, recipe_conf, filtered_results):
            self.evaluate_group_results(recipe, recipe_conf, group)

    def filter_results(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        results: List[PerfMeasurementResults],
    ) -> List[PerfMeasurementResults]:
        return results

    def group_results(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        results: List[PerfMeasurementResults],
    ) -> List[List[PerfMeasurementResults]]:
        for result in results:
            yield [result]

    def evaluate_group_results(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        results: List[PerfMeasurementResults],
    ):
        cumulative_result = ResultType.PASS
        comparisons = []

        baselines = self.get_baselines(recipe, recipe_conf, results)
        for result, baseline in zip(results, baselines):
            comparisons.extend(
                self.compare_result_with_baseline(
                    recipe, recipe_conf, result, baseline
                )
            )

        recipe.add_custom_result(
            BaselineEvaluationResult(
                comparisons=comparisons,
                recipe_conf=recipe_conf,
            )
        )

    def get_baselines(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        results: List[PerfMeasurementResults],
    ) -> List[PerfMeasurementResults]:
        return [
            self.get_baseline(recipe, recipe_conf, result) for result in results
        ]

    def get_baseline(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        result: PerfMeasurementResults,
    ) -> Optional[PerfMeasurementResults]:
        return None

    def get_threshold(
        self,
        baseline: PerfMeasurementResults,
        metric_name: str,
    ) -> Optional[float]:
        return None

    def compare_result_with_baseline(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        result: PerfMeasurementResults,
        baseline: PerfMeasurementResults,
    ) -> List[MetricComparison]:
        comparisons = []

        if self._metrics_to_evaluate:
            metrics_to_evaluate = [
                i for i in result.metrics if i in self._metrics_to_evaluate
            ]
        else:
            metrics_to_evaluate = result.metrics

        for metric in metrics_to_evaluate:
            comparisons.append(
                self.compare_metrics_with_threshold(
                    result=result,
                    baseline=baseline,
                    metric_name=metric,
                )
            )
        return comparisons

    def compare_metrics_with_threshold(self, result, baseline, metric_name):
        threshold = None
        diff = None

        if not baseline:
            comparison_result = ResultType.FAIL
            text = "No baseline found"
        elif (threshold := self.get_threshold(baseline, metric_name)) is None:
            comparison_result = ResultType.FAIL
            text = "No threshold found"
        else:
            diff = result_averages_difference(
                getattr(result, metric_name),
                getattr(baseline, metric_name),
            )
            direction = "higher" if diff >= 0 else "lower"

            comparison_result = (
                ResultType.PASS if abs(diff) <= threshold else ResultType.FAIL
            )
            text = (
                f"New {metric_name} average is {abs(diff):.2f}% {direction} from the baseline. "
                f"Allowed difference: {threshold}%"
            )

        return MetricComparison(
            measurement_type=result.measurement.__class__.__name__,
            current_result=result,
            baseline_result=baseline,
            threshold=threshold,
            metric_name=metric_name,
            difference=diff,
            comparison_result=comparison_result,
            text=text,
        )
