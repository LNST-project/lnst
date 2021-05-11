from lnst.RecipeCommon.BaseResultEvaluator import BaseResultEvaluator

class RatePingEvaluator(BaseResultEvaluator):
    def __init__(self, min_rate=None, max_rate=None, rate=None):
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.rate = rate

        if min_rate is None and max_rate is None and rate is None:
            raise Exception('{} requires at least one of min_rate, '
                'max_rate and rate parameters specified'.format(
                    self.__class__.__name__)
                    )

    def evaluate_results(self, recipe, result):
        if result is None or 'rate' not in result:
            recipe.add_result(False, 'Insufficient data for the evaluation of Ping test')
            return

        result_status = True
        ping_rate = int(result['rate'])

        result_text = []

        if self.min_rate is not None:
            rate_text = 'measured rate {} is {} than min_rate({})'
            if ping_rate < int(self.min_rate):
                result_status = False
                result_text.append(
                    rate_text.format(ping_rate, 'less', self.min_rate)
                    )
            else:
                result_text.append(
                    rate_text.format(ping_rate, 'more', self.min_rate)
                    )

        if self.max_rate is not None:
            rate_text = 'measured rate {} is {} than max_rate({})'
            if ping_rate > int(self.max_rate):
                result_status = False
                result_text.append(
                    rate_text.format(ping_rate, 'more', self.max_rate)
                    )
            else:
                result_text.append(
                    rate_text.format(ping_rate, 'less', self.max_rate)
                    )

        if self.rate is not None:
            rate_text = 'measured rate {} is {} rate({})'
            if ping_rate != int(self.rate):
                result_status = False
                result_text.append(
                    rate_text.format(ping_rate, 'different than', self.rate)
                    )
            else:
                result_text.append(
                    rate_text.format(ping_rate, 'equal to', self.rate)
                    )

        recipe.add_result(result_status, "\n".join(result_text))
