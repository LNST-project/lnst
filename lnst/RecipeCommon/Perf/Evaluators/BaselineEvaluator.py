from lnst.RecipeCommon.BaseResultEvaluator import BaseResultEvaluator


class BaselineEvaluator(BaseResultEvaluator):
    def evaluate_results(self, recipe, recipe_conf, results):
        filtered_results = self.filter_results(recipe, recipe_conf, results)

        for group in self.group_results(recipe, recipe_conf, filtered_results):
            self.evaluate_group_results(recipe, recipe_conf, group)

    def filter_results(self, recipe, recipe_conf, results):
        return results

    def group_results(self, recipe, recipe_conf, results):
        for result in results:
            yield [result]

    def evaluate_group_results(self, recipe, recipe_conf, results):
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

    def describe_group_results(self, recipe, recipe_conf, results):
        return []

    def get_baselines(self, recipe, recipe_conf, results):
        return [self.get_baseline(recipe, recipe_conf, result) for result in results]

    def get_baseline(self, recipe, recipe_conf, result):
        return None

    def compare_result_with_baseline(self, recipe, recipe_conf, result, baseline):
        return False, ["Result to baseline comparison not implemented"]
