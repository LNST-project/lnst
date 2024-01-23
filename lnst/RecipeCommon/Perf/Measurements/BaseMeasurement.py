class BaseMeasurement(object):
    def __init__(self, recipe_conf=None):
        self._recipe_conf = recipe_conf

    @property
    def name(self):
        return self.__class__.__name__

    @property
    def version(self):
        raise NotImplementedError()

    @property
    def recipe_conf(self):
        return self._recipe_conf

    def start(self):
        raise NotImplementedError()

    def simulate_start(self):
        return self.start()

    def finish(self):
        raise NotImplementedError()

    def simulate_finish(self):
        return self.finish()

    def collect_results(self):
        raise NotImplementedError()

    def collect_simulated_results(self):
        return self.collect_results()

    @classmethod
    def report_results(cls, recipe, results):
        raise NotImplementedError()

    @classmethod
    def aggregate_results(cls, first, second):
        raise NotImplementedError()

    def __repr__(self):
        return "{}({})".format(
            self.__class__.__name__,
            repr(self.recipe_conf),
        )
