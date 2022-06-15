import logging
from collections import OrderedDict
from typing import Any, List, Dict

from lnst.Common.LnstError import LnstError
from lnst.Common.Logs import log_exc_traceback
from lnst.Controller.Recipe import BaseRecipe
from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import (
    BaseMeasurement,
    BaseMeasurementResults,
)
from lnst.RecipeCommon.Perf.Measurements.IperfFlowMeasurement import FlowMeasurementResults
from lnst.RecipeCommon.Perf.Results import EmptySlice

from lnst.RecipeCommon.Perf.PerfTestMixins import (
    BasePerfTestTweakMixin,
    BasePerfTestIterationTweakMixin,
)
from lnst.RecipeCommon.BaseResultEvaluator import BaseResultEvaluator


class RecipeConf(object):
    def __init__(
        self,
        measurements: List[BaseMeasurement],
        iterations: int,
        parent_recipe_config: Any = None,
    ):
        self._measurements = measurements
        self._evaluators = dict()
        self._iterations = iterations
        self._parent_recipe_config = parent_recipe_config

    @property
    def measurements(self):
        return self._measurements

    @property
    def evaluators(self):
        return dict(self._evaluators)

    def register_evaluators(
        self,
        measurement: BaseMeasurement,
        evaluators: List[BaseResultEvaluator],
    ):
        if measurement not in self.measurements:
            raise LnstError(
                "Can't register evaluators for an unknown measurement"
            )

        self._evaluators[measurement] = list(evaluators)

    @property
    def iterations(self):
        return self._iterations

    @property
    def parent_recipe_config(self):
        return self._parent_recipe_config


class RecipeResults(object):
    def __init__(self, recipe_conf: RecipeConf):
        self._recipe_conf = recipe_conf
        self._results = OrderedDict()
        self._aggregated_results = OrderedDict()

    @property
    def recipe_conf(self) -> RecipeConf:
        return self._recipe_conf

    @property
    def results(self) -> Dict[BaseMeasurement, List[BaseMeasurementResults]]:
        return self._results

    @property
    def aggregated_results(
        self,
    ) -> Dict[BaseMeasurement, BaseMeasurementResults]:
        return self._aggregated_results

    def add_measurement_results(
        self, measurement: BaseMeasurement, new_results: BaseMeasurementResults
    ):
        if measurement not in self._results:
            self._results[measurement] = [new_results]
        else:
            self._results[measurement].append(new_results)

        aggregated_results = self._aggregated_results.get(measurement, None)
        aggregated_results = measurement.aggregate_results(
            aggregated_results, new_results
        )
        self._aggregated_results[measurement] = aggregated_results

    """
        Function returns end timestamp of warmup period and start of warm down period.
        That results to slice measurement result just for "interesting" part not including 
        warm up and warm down periods.
    """
    def _get_measurement_timestamps(self, flows: List[BaseMeasurementResults]):
        # [-1] bellow to get last measurement, measurements are started in sequence, so valid interval depends
        # on the last measurement
        if isinstance(flows[-1], FlowMeasurementResults):
            logging.debug(f"Results alignment: Using times of flow measurement: {flows[-1]}")
            return flows[-1].warmup_end, flows[-1].warmdown_start
        else:
            logging.debug("Results alignment: Using times from latest start and earliest end")
            return max([res.start_timestamp for res in flows]), min([res.end_timestamp for res in flows])

    @property
    def time_aligned_results(self) -> "RecipeResults":
        timestamps = []
        for i in range(self.recipe_conf.iterations):
            iteration_results_group = [
                measurement_iteration_result
                for measurement_results in self.results.values()
                for measurement_iteration_result in measurement_results[i]
            ]

            real_times = self._get_measurement_timestamps(iteration_results_group)
            timestamps.append(real_times)

        aligned_recipe_results = RecipeResults(self._recipe_conf)
        for measurement, measurement_results in self.results.items():
            for i, measurement_iteration in enumerate(measurement_results):
                aligned_measurement_results = []
                for result in measurement_iteration:

                    aligned_measurement_result = result.time_slice(
                        *timestamps[i]
                    )
                    if aligned_measurement_result not in aligned_measurement_results:
                        aligned_measurement_results.append(
                            aligned_measurement_result
                        )

                aligned_recipe_results.add_measurement_results(
                    measurement, aligned_measurement_results
                )

        return aligned_recipe_results


class Recipe(
    BasePerfTestTweakMixin, BasePerfTestIterationTweakMixin, BaseRecipe
):
    def perf_test(self, recipe_conf: RecipeConf):
        results = RecipeResults(recipe_conf)

        self.apply_perf_test_tweak(recipe_conf)
        self.describe_perf_test_tweak(recipe_conf)

        try:
            for i in range(recipe_conf.iterations):
                self.perf_test_iteration(recipe_conf, results)
        finally:
            self.remove_perf_test_tweak(recipe_conf)

        return results

    def perf_test_iteration(
        self, recipe_conf: RecipeConf, results: RecipeResults
    ):
        self.apply_perf_test_iteration_tweak(recipe_conf)
        self.describe_perf_test_iteration_tweak(recipe_conf)

        try:
            for measurement in recipe_conf.measurements:
                measurement.start()
            for measurement in reversed(recipe_conf.measurements):
                measurement.finish()
            for measurement in recipe_conf.measurements:
                measurement_results = measurement.collect_results()
                results.add_measurement_results(
                    measurement, measurement_results
                )
        finally:
            self.remove_perf_test_iteration_tweak(recipe_conf)

    def describe_perf_test_iteration_tweak(self, recipe_conf: RecipeConf):
        description = self.generate_perf_test_iteration_tweak_description(
            recipe_conf
        )
        self.add_result(True, "\n".join(description))

    def perf_report_and_evaluate(self, results: RecipeResults):
        try:
            aligned_results = results.time_aligned_results
        except EmptySlice:
            logging.error("Result time alignment impossible, falling back to unaligned results")
            log_exc_traceback()
            aligned_results = results


        self.perf_report(aligned_results)
        self.perf_evaluate(aligned_results)

    def perf_report(self, recipe_results: RecipeResults):
        if not recipe_results:
            self.add_result(False, "No results available to report.")
            return

        for measurement, results in list(
            recipe_results.aggregated_results.items()
        ):
            measurement.report_results(self, results)

    def perf_evaluate(self, recipe_results: RecipeResults):
        if not recipe_results:
            self.add_result(False, "No results available to evaluate.")
            return

        recipe_conf = recipe_results.recipe_conf

        for measurement, results in list(
            recipe_results.aggregated_results.items()
        ):
            evaluators = recipe_conf.evaluators.get(measurement, [])
            for evaluator in evaluators:
                evaluator.evaluate_results(self, recipe_conf, results)

            if len(evaluators) == 0:
                logging.debug(
                    "No evaluator registered for measurement {}".format(
                        measurement
                    )
                )
