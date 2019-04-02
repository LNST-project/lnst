import logging
from collections import OrderedDict

from lnst.Common.LnstError import LnstError
from lnst.Controller.Recipe import BaseRecipe
from lnst.RecipeCommon.Perf.Results import SequentialPerfResult
from lnst.RecipeCommon.Perf.Results import ParallelPerfResult

class RecipeConf(object):
    def __init__(self, measurements, iterations):
        self._measurements = measurements
        self._evaluators = dict()
        self._iterations = iterations

    @property
    def measurements(self):
        return self._measurements

    @property
    def evaluators(self):
        return dict(self._evaluators)

    def register_evaluators(self, measurement, evaluators):
        if measurement not in self.measurements:
            raise LnstError("Can't register evaluators for an unknown measurement")

        self._evaluators[measurement] = list(evaluators)

    @property
    def iterations(self):
        return self._iterations

class RecipeResults(object):
    def __init__(self, perf_conf):
        self._perf_conf = perf_conf
        self._results = OrderedDict()

    @property
    def perf_conf(self):
        return self._perf_conf

    @property
    def results(self):
        return self._results

    def add_measurement_results(self, measurement, new_results):
        aggregated_results = self._results.get(measurement, None)
        aggregated_results = measurement.aggregate_results(
                aggregated_results, new_results)
        self._results[measurement] = aggregated_results

class Recipe(BaseRecipe):
    def perf_test(self, recipe_conf):
        results = RecipeResults(recipe_conf)

        for i in range(recipe_conf.iterations):
            for measurement in recipe_conf.measurements:
                measurement.start()
            for measurement in reversed(recipe_conf.measurements):
                measurement.finish()
            for measurement in recipe_conf.measurements:
                measurement_results = measurement.collect_results()
                results.add_measurement_results(
                        measurement, measurement_results)

        return results

    def perf_report_and_evaluate(self, results):
        self.perf_report(results)

        self.perf_evaluate(results)

    def perf_report(self, recipe_results):
        if not recipe_results:
            self.add_result(False, "No results available to report.")
            return

        for measurement, results in recipe_results.results.items():
            measurement.report_results(self, results)

    def perf_evaluate(self, recipe_results):
        if not recipe_results:
            self.add_result(False, "No results available to evaluate.")
            return

        perf_conf = recipe_results.perf_conf

        for measurement, results in recipe_results.results.items():
            evaluators = perf_conf.evaluators.get(measurement, [])
            for evaluator in evaluators:
                evaluator.evaluate_results(self, results)

            if len(evaluators) == 0:
                logging.debug("No evaluator registered for measurement {}"
                              .format(measurement))
