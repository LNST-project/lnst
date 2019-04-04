from __future__ import division

from .BaseEvaluator import BaseEvaluator

from ..Measurements.BaseCPUMeasurement import (
    CPUMeasurementResults,
    AggregatedCPUMeasurementResults,
)


class BaselineCPUAverageEvaluator(BaseEvaluator):
    def __init__(self, pass_difference):
        self._pass_difference = pass_difference

    def evaluate_results(self, recipe, results):
        for result in results:
            baseline = self.get_baseline(recipe, result)
            self._compare_result_with_baseline(recipe, result, baseline)

    def get_baseline(self, recipe, result):
        return None

    def _compare_result_with_baseline(self, recipe, result, baseline):
        comparison_result = True
        result_text = [
            "CPU Baseline average evaluation".format(),
            "Configured {}% difference as acceptable".format(self._pass_difference),
        ]
        if baseline is None:
            comparison_result = False
            result_text.append("No baseline found for this CPU measurement")
        else:
            result_text.append("I don't know how to compare CPU averages yet!!!")
            comparison_result = False

        recipe.add_result(comparison_result, "\n".join(result_text))
