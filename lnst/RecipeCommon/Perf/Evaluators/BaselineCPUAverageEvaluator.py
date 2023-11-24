from __future__ import division
from typing import List, Dict, Optional


from lnst.Controller.Recipe import BaseRecipe

from lnst.RecipeCommon.Perf.Recipe import RecipeConf as PerfRecipeConf
from lnst.RecipeCommon.Perf.Measurements.Results import (
    BaseMeasurementResults as PerfMeasurementResults,
)
from lnst.RecipeCommon.Perf.Evaluators.BaselineEvaluator import BaselineEvaluator


class BaselineCPUAverageEvaluator(BaselineEvaluator):
    def __init__(
        self,
        metrics_to_evaluate: Optional[List[str]] = None,
        evaluation_filter: Optional[Dict[str, str]] = None,
    ):
        super().__init__(metrics_to_evaluate)
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
