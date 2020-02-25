from lnst.RecipeCommon.Perf.Evaluators.BaseEvaluator import BaseEvaluator


class BaselineEvaluator(BaseEvaluator):
    def evaluate_results(self, recipe, results):
        filtered_results = self.filter_results(recipe, results)

        for group in self.group_results(recipe, filtered_results):
            self.evaluate_group_results(recipe, group)

    def filter_results(self, recipe, results):
        return results

    def group_results(self, recipe, results):
        for result in results:
            yield [result]

    def evaluate_group_results(self, recipe, results):
        comparison_result = True
        result_text = self.describe_group_results(recipe, results)

        baselines = self.get_baselines(recipe, results)
        for result, baseline in zip(results, baselines):
            comparison, text = self.compare_result_with_baseline(
                recipe, result, baseline
            )
            comparison_result = comparison_result and comparison
            result_text.extend(text)

        recipe.add_result(comparison_result, "\n".join(result_text))

    def describe_group_results(self, recipe, results):
        return []

    def get_baselines(self, recipe, results):
        return [self.get_baseline(recipe, result) for result in results]

    def get_baseline(self, recipe, result):
        return None

    def compare_result_with_baseline(self, recipe, result, baseline):
        return False, ["Result to baseline comparison not implemented"]
