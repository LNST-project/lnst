class BaseMeasurement(object):
    def __init__(self, conf):
        self._conf = conf

    @property
    def conf(self):
        return self._conf

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
