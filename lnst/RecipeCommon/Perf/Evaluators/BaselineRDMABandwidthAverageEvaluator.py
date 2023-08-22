from lnst.Controller.Recipe import BaseRecipe
from lnst.Controller.RecipeResults import ResultType
from lnst.RecipeCommon.Perf.Evaluators.BaselineEvaluator import BaselineEvaluator, MetricComparison
from lnst.RecipeCommon.Perf.Measurements.Results import RDMABandwidthMeasurementResults


class BaselineRDMABandwidthAverageEvaluator(BaselineEvaluator):

    def __init__(self, thresholds: dict):
        self._thresholds = thresholds

    def compare_result_with_baseline(
        self,
        recipe: BaseRecipe,
        recipe_conf: "EnrtConfiguration",
        result: RDMABandwidthMeasurementResults,
        baseline: RDMABandwidthMeasurementResults,
        result_index: int = 0,
    ) -> list[MetricComparison]:
        metric_name = f"{result_index}_bandwidth"

        if baseline is None:
            return [
                MetricComparison(
                    metric_name=metric_name,
                    result=ResultType.FAIL,
                    text=f"{self.__class__.__name__} FAIL:\n Metric {metric_name} baseline not found",
                )
            ]
        elif (threshold := self._thresholds.get(metric_name, None)) is None:
            return [
                MetricComparison(
                    metric_name=metric_name,
                    result=ResultType.FAIL,
                    text=f"{self.__class__.__name__}\nFAIL: Metric {metric_name} threshold not found",
                )
            ]

        difference = ((result.bandwidth.average / baseline.bandwidth.average) * 100) - 100
        direction = "higher" if difference >= 0 else "lower"
        text = [
            f"{self.__class__.__name__} of {metric_name}",
            f"Baseline: {baseline.bandwidth.average} MiB/s",
            f"Measured: {result.bandwidth.average} MiB/s",
            f"{abs(difference):2f}% {direction} than baseline",
            f"Allowed difference: {threshold}%",
        ]
        if difference > threshold:
            comparison = ResultType.WARNING
            text[0] = f"IMPROVEMENT: {text[0]}"
        elif difference >= -threshold:
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
