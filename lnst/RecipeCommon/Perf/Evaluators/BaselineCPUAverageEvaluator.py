from __future__ import division
from typing import List, Tuple, Dict


from lnst.Controller.Recipe import BaseRecipe
from lnst.RecipeCommon.Perf.Recipe import RecipeConf as PerfRecipeConf
from lnst.RecipeCommon.Perf.Results import result_averages_difference
from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import (
    BaseMeasurementResults as PerfMeasurementResults,
)
from lnst.RecipeCommon.Perf.Evaluators.BaselineEvaluator import (
    BaselineEvaluator,
)


class BaselineCPUAverageEvaluator(BaselineEvaluator):
    def __init__(
        self, pass_difference: int, evaluation_filter: Dict[str, str] = None
    ):
        self._pass_difference = pass_difference
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
            ),
            "Configured {diff}% difference as acceptable".format(
                diff=self._pass_difference
            ),
        ]

    def compare_result_with_baseline(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        result: PerfMeasurementResults,
        baseline: PerfMeasurementResults,
    ) -> Tuple[bool, List[str]]:
        comparison = True
        text = []
        if baseline is None:
            comparison = False
            text.append(
                "CPU {cpuid}: no baseline found".format(cpuid=result.cpu)
            )
        else:
            try:
                difference = result_averages_difference(
                    result.utilization, baseline.utilization
                )

                text.append(
                    "CPU {cpuid}: utilization {diff:.2f}% {direction} than baseline".format(
                        cpuid=result.cpu,
                        diff=abs(difference),
                        direction="higher" if difference >= 0 else "lower",
                    )
                )

                if abs(difference) > self._pass_difference:
                    comparison = False
            except ZeroDivisionError:
                text.append(
                    "CPU {cpuid}: zero division by baseline".format(
                        cpuid=result.cpu
                    )
                )
        return comparison, text
