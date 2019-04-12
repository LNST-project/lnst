from __future__ import division

from .BaseEvaluator import BaseEvaluator

from ..Measurements.BaseCPUMeasurement import (
    CPUMeasurementResults,
    AggregatedCPUMeasurementResults,
)
from ..Results import result_averages_difference


class BaselineCPUAverageEvaluator(BaseEvaluator):
    def __init__(self, pass_difference):
        self._pass_difference = pass_difference

    def evaluate_results(self, recipe, results):
        for host_results in self._divide_results_by_host(results).values():
            self._evaluate_host_results(recipe, host_results)

    def get_baseline(self, recipe, result):
        return None

    def _divide_results_by_host(self, results):
        results_by_host = {}
        for result in results:
            if result.host not in results_by_host:
                results_by_host[result.host] = []
            results_by_host[result.host].append(result)
        return results_by_host

    def _evaluate_host_results(self, recipe, host_results):
        comparison_result = True
        result_text = [
            "CPU Baseline average evaluation for Host {hostid}:".format(
                hostid=host_results[0].host.hostid
            ),
            "Configured {diff}% difference as acceptable".format(
                diff=self._pass_difference
            ),
        ]
        pairs = [
            (result, self.get_baseline(recipe, result))
            for result in host_results
        ]
        for result, baseline in pairs:
            if baseline is None:
                result_text.append(
                    "CPU {cpuid}: no baseline found for ".format(
                        cpuid=result.cpu
                    )
                )
            else:
                try:
                    difference = result_averages_difference(
                        result.utilization, baseline.utilization
                    )

                    if abs(difference) > self._pass_difference:
                        comparison_result = False

                    result_text.append(
                        "CPU {cpuid}: utilization {diff:.2f}% {direction} than baseline".format(
                            cpuid=result.cpu,
                            diff=abs(difference),
                            direction="higher" if difference >= 0 else "lower",
                        )
                    )
                except ZeroDivisionError:
                    result_text.append(
                        "CPU {cpuid}: zero division by baseline".format(
                            cpuid=result.cpu
                        )
                    )

        recipe.add_result(comparison_result, "\n".join(result_text))
