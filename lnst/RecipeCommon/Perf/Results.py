from lnst.Common.LnstError import LnstError
from lnst.Common.Utils import std_deviation

class PerfStatMixin(object):
    @property
    def average(self):
        return float(self.value) / self.duration

    @property
    def std_deviation(self):
        return std_deviation([i.average for i in self])

class PerfResult(PerfStatMixin):
    @property
    def value(self):
        raise NotImplementedError()

    @property
    def duration(self):
        raise NotImplementedError()

    @property
    def unit(self):
        raise NotImplementedError()

class PerfInterval(PerfResult):
    def __init__(self, value, duration, unit):
        self._value = value
        self._duration = duration
        self._unit = unit

    @property
    def value(self):
        return self._value

    @property
    def duration(self):
        return self._duration

    @property
    def unit(self):
        return self._unit

    @property
    def std_deviation(self):
        return 0

    def __str__(self):
        return "{:.2f} {} in {:.2f} seconds".format(
                float(self.value), self.unit, float(self.duration))

class PerfList(list):
    def __init__(self, iterable=[]):
        for i, item in enumerate(iterable):
            self._validate_item_type(item)

            if i == 0:
                unit = item.unit

            if item.unit != unit:
                raise LnstError("PerfList items must have the same unit.")

        super(PerfList, self).__init__(iterable)

    def _validate_item(self, item):
        self._validate_item_type(item)

        if len(self) > 0 and item.unit != self[0].unit:
            raise LnstError("PerfList items must have the same unit.")

    def _validate_item_type(self, item):
        if (not isinstance(item, PerfInterval) and
            not isinstance(item, PerfList)):
            raise LnstError("{} only accepts PerfInterval or PerfList objects."
                            .format(self.__class__.__name__))

    def append(self, item):
        self._validate_item(item)

        super(PerfList, self).append(item)

    def extend(self, iterable):
        for i in iterable:
            self._validate_item(i)

        super(PerfList, self).extend(iterable)

    def insert(self, index, item):
        self._validate_item(item)

        super(PerfList, self).insert(index, item)

    def __add__(self, iterable):
        for i in iterable:
            self._validate_item(i)

        super(PerfList, self).__add__(iterable)

    def __iadd__(self, iterable):
        for i in iterable:
            self._validate_item(i)

        super(PerfList, self).__iadd__(iterable)

    def __setitem__(self, i, item):
        self._validate_item(item)

        super(PerfList, self).__setitem__(i, item)

    def __setslice__(self, i, j, iterable):
        for i in iterable:
            self._validate_item(i)

        super(PerfList, self).__setslice__(i, j, iterable)

class SequentialPerfResult(PerfResult, PerfList):
    @property
    def value(self):
        return sum([i.value for i in self])

    @property
    def duration(self):
        return sum([i.duration for i in self])

    @property
    def unit(self):
        if len(self) > 0:
            return self[0].unit
        else:
            return None

class ParallelPerfResult(PerfResult, PerfList):
    @property
    def value(self):
        return sum([i.value for i in self])

    @property
    def duration(self):
        return max([i.duration for i in self])

    @property
    def unit(self):
        if len(self) > 0:
            return self[0].unit
        else:
            return None

def result_averages_difference(a, b):
    if a is None or b is None:
        return None
    return 100 - ((a.average / b.average) * 100)
