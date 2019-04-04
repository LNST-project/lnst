class BaseMeasurement(object):
    def __init__(self, conf):
        self._conf = conf

    @property
    def name(self):
        return self.__class__.__name__

    @property
    def version(self):
        raise NotImplementedError()

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


class BaseMeasurementResults(object):
    def __init__(self, measurement):
        self._measurement = measurement

    @property
    def measurement(self):
        return self._measurement
