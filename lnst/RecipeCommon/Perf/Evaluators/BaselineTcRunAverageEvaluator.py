from lnst.Controller.RecipeResults import ResultType
from lnst.RecipeCommon.Perf.Evaluators.BaselineEvaluator import BaselineEvaluator, MetricComparison
from lnst.RecipeCommon.Perf.Measurements.Results import TcRunMeasurementResults
from lnst.Recipes.ENRT.TrafficControlRecipe import TrafficControlRecipe, TcRecipeConfiguration


class BaselineTcRunAverageEvaluator(BaselineEvaluator):

    def __init__(self, thresholds: dict):
        self._thresholds = thresholds

    def compare_result_with_baseline(
            self,
            recipe: TrafficControlRecipe,
            recipe_conf: TcRecipeConfiguration,
            result: TcRunMeasurementResults,
            baseline: TcRunMeasurementResults,
            result_index: int = 0,
    ) -> list[MetricComparison]:

        metric_name = f"{result_index}_time_taken"

        if baseline is None:
            return [
                MetricComparison(
                    metric_name=metric_name,
                    result=ResultType.FAIL,
                    text=f"{self.__class__.__name__} FAIL:\n {result.device.name} {metric_name} baseline not found",
                )
            ]
        elif (threshold := self._thresholds.get(metric_name, None)) is not None:
            difference = ((result.time_taken / baseline.time_taken) * 100 ) - 100
            direction = "higher" if difference >= 0 else "lower"
            text = [
                f"{self.__class__.__name__} of tc run with {metric_name}",
                f"{result.description}",
                f"baseline time_taken={baseline.time_taken}",
                f"{difference:2f} {direction} than baseline ",
                f"Allowed differences: {threshold}% ",
            ]
            if difference < -threshold:
                comparison = ResultType.WARNING
                text[0] = f"IMPROVEMENT: {text[0]}"
            elif difference <= threshold:
                comparison = ResultType.PASS
                text[0] = f"PASS: {text[0]}"
            else:
                comparison = ResultType.FAIL
                text[0] = f"FAIL: {text[0]}"

            return [
                MetricComparison(
                    metric_name=metric_name,
                    result=comparison,
                    text="\n".join(text)
                )
            ]
        else:
            return [
                MetricComparison(
                    metric_name=metric_name,
                    result=ResultType.FAIL,
                    text=f"{self.__class__.__name__}\nFAIL: {result.device.name} {metric_name} no threshold found",
                )
            ]

