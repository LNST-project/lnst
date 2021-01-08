from typing import List, Any

from lnst.Controller.Recipe import BaseRecipe


class BaseResultEvaluator(object):
    def evaluate_results(
        self,
        recipe: BaseRecipe,
        recipe_conf: Any,
        results: List[Any],
    ):
        raise NotImplementedError()
