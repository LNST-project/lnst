from typing import List, Tuple
from lnst.Controller.Recipe import BaseRecipe
from lnst.RecipeCommon.BaseResultEvaluator import BaseResultEvaluator
from lnst.RecipeCommon.Perf.Recipe import RecipeConf as PerfRecipeConf
from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import (
    BaseMeasurementResults as PerfMeasurementResults,
)


class BaselineEvaluator(BaseResultEvaluator):
    def evaluate_results(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        results: List[PerfMeasurementResults],
    ):
        filtered_results = self.filter_results(recipe, recipe_conf, results)

        for group in self.group_results(recipe, recipe_conf, filtered_results):
            self.evaluate_group_results(recipe, recipe_conf, group)

    def filter_results(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        results: List[PerfMeasurementResults],
    ) -> List[PerfMeasurementResults]:
        return results

    def group_results(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        results: List[PerfMeasurementResults],
    ) -> List[List[PerfMeasurementResults]]:
        for result in results:
            yield [result]

    def evaluate_group_results(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        results: List[PerfMeasurementResults],
    ):
        comparison_result = True
        result_text = self.describe_group_results(recipe, recipe_conf, results)

        baselines = self.get_baselines(recipe, recipe_conf, results)
        for result, baseline in zip(results, baselines):
            comparison, text = self.compare_result_with_baseline(
                recipe, recipe_conf, result, baseline
            )
            comparison_result = comparison_result and comparison
            result_text.extend(text)

        recipe.add_result(comparison_result, "\n".join(result_text))

    def describe_group_results(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        results: List[PerfMeasurementResults],
    ) -> List[str]:
        return []

    def get_baselines(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        results: List[PerfMeasurementResults],
    ) -> List[PerfMeasurementResults]:
        return [self.get_baseline(recipe, recipe_conf, result) for result in results]

    def get_baseline(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        result: PerfMeasurementResults,
    ) -> PerfMeasurementResults:
        return None

    def compare_result_with_baseline(
        self,
        recipe: BaseRecipe,
        recipe_conf: PerfRecipeConf,
        result: PerfMeasurementResults,
        baseline: PerfMeasurementResults,
    ) -> Tuple[bool, List[str]]:
        return False, ["Result to baseline comparison not implemented"]
