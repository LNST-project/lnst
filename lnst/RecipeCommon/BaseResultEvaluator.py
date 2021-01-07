class BaseResultEvaluator(object):
    def evaluate_results(self, recipe, recipe_conf, results):
        raise NotImplementedError()
