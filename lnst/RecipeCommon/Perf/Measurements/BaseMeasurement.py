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

    def finish(self):
        raise NotImplementedError()

    def collect_results(self):
        raise NotImplementedError()

    @classmethod
    def report_results(recipe, results):
        raise NotImplementedError()

    @classmethod
    def aggregate_results(first, second):
        raise NotImplementedError()

    def __repr__(self):
        return "{}({})".format(
            self.__class__.__name__,
            repr(self.recipe_conf),
        )


class BaseMeasurementResults(object):
    def __init__(self, measurement: BaseMeasurement):
        self._measurement = measurement

    @property
    def measurement(self) -> BaseMeasurement:
        return self._measurement

    def align_data(self, start, end):
        return self
