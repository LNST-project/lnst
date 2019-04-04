from __future__ import division

from .BaseEvaluator import BaseEvaluator

from ..Measurements.BaseFlowMeasurement import (
    FlowMeasurementResults,
    AggregatedFlowMeasurementResults,
)


class BaselineFlowAverageEvaluator(BaseEvaluator):
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
            "Flow {} Baseline average evaluation".format(result.flow),
            "Configured {}% difference as acceptable".format(self._pass_difference),
        ]
        if baseline is None:
            comparison_result = False
            result_text.append("No baseline found for this flow")
        else:
            generator_diff = _result_averages_difference(
                result.generator_results,
                baseline.generator_results)
            result_text.append(
                    "Generator average is {:.2f}% different from the baseline generator average"
                .format(generator_diff))

            receiver_diff = _result_averages_difference(
                result.receiver_results,
                baseline.receiver_results)
            result_text.append(
                    "Receiver average is {:.2f}% different from the baseline receiver average"
                .format(receiver_diff))

            if (
                abs(generator_diff) > self._pass_difference
                or abs(receiver_diff) > self._pass_difference
            ):
                comparison_result = False

        recipe.add_result(comparison_result, "\n".join(result_text))


def _result_averages_difference(a, b):
    return 100 - ((a.average / b.average)*100)
