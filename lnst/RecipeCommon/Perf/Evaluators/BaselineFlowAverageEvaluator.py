from __future__ import division

from lnst.RecipeCommon.Perf.Evaluators.BaselineEvaluator import (
    BaselineEvaluator,
)

from lnst.RecipeCommon.Perf.Results import result_averages_difference


class BaselineFlowAverageEvaluator(BaselineEvaluator):
    def __init__(self, pass_difference, metrics_to_evaluate=None):
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

    def describe_group_results(self, recipe, recipe_conf, results):
        result = results[0]
        return [
            "Baseline average evaluation of flow:",
            "{}".format(result.flow),
            "Configured {}% difference as acceptable".format(
                self._pass_difference
            ),
        ]

    def compare_result_with_baseline(self, recipe, recipe_conf, result, baseline):
        comparison_result = True
        result_text = []
        if baseline is None:
            comparison_result = False
            result_text.append("No baseline found for this flow")
        else:
            for i in self._metrics_to_evaluate:
                comparison, text = self._average_diff_comparison(
                    name="{} average".format(i),
                    target=getattr(result, i),
                    baseline=getattr(baseline, i),
                )
                result_text.append(text)
                comparison_result = comparison_result and comparison
        return comparison_result, result_text

    def _average_diff_comparison(self, name, target, baseline):
        difference = result_averages_difference(target, baseline)
        result_text = "New {name} is {diff:.2f}% {direction} from the baseline {name}".format(
            name=name,
            diff=abs(difference),
            direction="higher" if difference >= 0 else "lower",
        )
        comparison = abs(difference) <= self._pass_difference
        return comparison, result_text
