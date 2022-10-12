from typing import List, Tuple
from lnst.Controller.Recipe import BaseRecipe
from lnst.Controller.RecipeResults import ResultType, Result
from lnst.RecipeCommon.BaseResultEvaluator import BaseResultEvaluator
from lnst.RecipeCommon.Perf.Recipe import RecipeConf as PerfRecipeConf
from lnst.RecipeCommon.Perf.Measurements.Results import (
    BaseMeasurementResults as PerfMeasurementResults,
)


class BaselineEvaluationResult(Result):
    pass


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
        cumulative_result = ResultType.PASS
        comparisons = []
        result_text = self.describe_group_results(recipe, recipe_conf, results)

        baselines = self.get_baselines(recipe, recipe_conf, results)
        result_index = len(recipe.current_run.results)
        for i, (result, baseline) in enumerate(zip(results, baselines)):
            comparison_result, text = self.compare_result_with_baseline(
                recipe, recipe_conf, result, baseline, result_index
            )
            cumulative_result = ResultType.max_severity(
                cumulative_result,
                comparison_result,
            )
            result_text.extend(text)
            comparisons.append(
                {
                    "current_result": result,
                    "baseline_result": baseline,
                    "comparison_result": comparison_result,
                    "text": text,
                    "recipe_conf": recipe_conf,
                }
            )

        recipe.add_custom_result(
            BaselineEvaluationResult(
                cumulative_result,
                "\n".join(result_text),
                data={"comparisons": comparisons},
            )
        )

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
        result_index: int = 0
    ) -> Tuple[ResultType, List[str]]:
        return ResultType.FAIL, ["Result to baseline comparison not implemented"]
