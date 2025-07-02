from typing import Any, List

from lnst.Controller import BaseRecipe
from lnst.Controller.RecipeResults import ResultType
from lnst.RecipeCommon.BaseResultEvaluator import BaseResultEvaluator
from lnst.RecipeCommon.Perf.Measurements.Results.TcRunMeasurementResults import TcRunMeasurementResults


class MaxTimeTakenEvaluator(BaseResultEvaluator):

    def __init__(self, max_time):
        super().__init__()
        self._max_time = max_time

    def _check_interval(self, timed_run: TcRunMeasurementResults) -> ResultType:
        if timed_run.rule_install_rate.duration <= self._max_time:
            return ResultType.PASS
        return ResultType.FAIL

    def evaluate_results(
            self,
            recipe: BaseRecipe,
            recipe_conf: Any,
            results: List[TcRunMeasurementResults]
    ):
        for timed_run in results:
            result_text = [
                f"MaxTimeTaken evaluation of timed run, max_time={self._max_time}s",
                timed_run.describe(),
            ]
            rtype = self._check_interval(timed_run)

            if rtype == ResultType.PASS:
                result_text.append(f"PASS: Runtime {timed_run.time_taken} <= {self._max_time}")
            else:
                result_text.append(f"FAIL: Runtime {timed_run.time_taken} > {self._max_time}")

            recipe.add_result(rtype, "\n".join(result_text))
