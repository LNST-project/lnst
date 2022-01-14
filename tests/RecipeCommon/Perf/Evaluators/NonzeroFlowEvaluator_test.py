from unittest import TestCase
from unittest.mock import Mock

from lnst.RecipeCommon.Perf.Evaluators.NonzeroFlowEvaluator import NonzeroFlowEvaluator
from tests.RecipeCommon.Perf.Evaluators.measurements_data import nonzero_flow, some_zero_flow


class RecipeMock(Mock):
    result = None

    def add_result(self, success, description):
        self.result = success


class NonzeroFlowEvaluatorTest(TestCase):
    def test_nonzero(self):
        evaluator = NonzeroFlowEvaluator()
        recipe = RecipeMock()

        evaluator.evaluate_results(recipe=recipe,
                                   recipe_conf=Mock(),
                                   results=[nonzero_flow])
        self.assertEqual(recipe.result, True, "evaluate_results did not return True with correct flow measurements")

    def test_empty(self):
        evaluator = NonzeroFlowEvaluator()
        recipe = RecipeMock()

        evaluator.evaluate_results(recipe=recipe,
                                   recipe_conf=Mock(),
                                   results=[])

        self.assertEqual(recipe.mock_calls, [], "evaluate_results entered the loop with empty results list")

    def test_zero(self):
        evaluator = NonzeroFlowEvaluator()
        recipe = RecipeMock()

        evaluator.evaluate_results(recipe=recipe,
                                   recipe_conf=Mock(),
                                   results=[some_zero_flow])
        self.assertEqual(recipe.result, False, "evaluate_results did not return False with some "
                                               "PerfIntervals equal to 0 in the  flow measurements")
