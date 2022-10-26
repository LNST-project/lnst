from __future__ import division
from typing import List, Dict


from lnst.Controller.Recipe import BaseRecipe
from lnst.Controller.RecipeResults import ResultType

from lnst.RecipeCommon.Perf.Recipe import RecipeConf as PerfRecipeConf
from lnst.RecipeCommon.Perf.Results import result_averages_difference
from lnst.RecipeCommon.Perf.Measurements.Results import (
    BaseMeasurementResults as PerfMeasurementResults,
)
from lnst.RecipeCommon.Perf.Evaluators.BaselineEvaluator import (
    BaselineEvaluator, MetricComparison
)


class BaselineCPUAverageEvaluator(BaselineEvaluator):
    def __init__(
        self, thresholds: dict, evaluation_filter: Dict[str, str] = None
    ):
        self._thresholds = thresholds
        self._evaluation_filter = evaluation_filter

    def filter_results(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        results: List[PerfMeasurementResults],
    ) -> List[PerfMeasurementResults]:
        if self._evaluation_filter is None:
            return results

        filtered = []
        for result in results:
            if (
                result.host.hostid in self._evaluation_filter
                and result.cpu in self._evaluation_filter[result.host.hostid]
            ):
                filtered.append(result)
        return filtered

    def group_results(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        results: List[PerfMeasurementResults],
    ) -> List[List[PerfMeasurementResults]]:
        results_by_host = self._divide_results_by_host(results)
        for host_results in results_by_host.values():
            yield host_results

    def _divide_results_by_host(self, results: List[PerfMeasurementResults]):
        results_by_host = {}
        for result in results:
            if result.host not in results_by_host:
                results_by_host[result.host] = []
            results_by_host[result.host].append(result)
        return results_by_host

    def describe_group_results(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        results: List[PerfMeasurementResults],
    ) -> List[str]:
        return [
            "CPU Baseline average evaluation for Host {hostid}:".format(
                hostid=results[0].host.hostid
            )
        ]

    def compare_result_with_baseline(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        result: PerfMeasurementResults,
        baseline: PerfMeasurementResults,
        result_index: int = 0
    ) -> List[MetricComparison]:
        comparison = ResultType.FAIL

        metric_name = f"{result_index}_utilization"

        if baseline is None:
            return [
                MetricComparison(
                    metric_name=metric_name,
                    result=ResultType.FAIL,
                    text=f"FAIL: CPU {result.cpu}: no baseline found",
                )
            ]
        elif (threshold := self._thresholds.get(metric_name, None)) is not None:
            try:
                difference = result_averages_difference(
                    result.utilization, baseline.utilization
                )

                text = (
                    "CPU {cpuid}: {metric_name} {diff:.2f}% {direction} than baseline. "
                    "Allowed difference: {threshold}%".format(
                        cpuid=result.cpu,
                        metric_name=metric_name,
                        diff=abs(difference),
                        direction="higher" if difference >= 0 else "lower",
                        threshold=threshold
                    )
                )

                if difference < -threshold:
                    comparison = ResultType.WARNING
                    text = "IMPROVEMENT: " + text
                elif difference <= threshold:
                    comparison = ResultType.PASS
                    text = "PASS: " + text
                else:
                    comparison = ResultType.FAIL
                    text = "FAIL: " + text
            except ZeroDivisionError:
                text = f"CPU {result.cpu}: {metric_name} zero division by baseline"
            return [
                MetricComparison(
                    metric_name=metric_name,
                    result=comparison,
                    text=text,
                )
            ]
        else:
            return [
                MetricComparison(
                    metric_name=metric_name,
                    result=ResultType.FAIL,
                    text=f"FAIL: CPU {result.cpu}: {metric_name} no threshold found",
                )
            ]
