from lnst.Common.LnstError import LnstError
from lnst.Common.Utils import std_deviation

class PerfStatMixin(object):
    @property
    def average(self):
        return float(self.value) / self.duration

    @property
    def std_deviation(self):
        return std_deviation([i.average for i in self])

class PerfInterval(PerfStatMixin):
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

class PerfList(list):
    _sub_type = None

    def __init__(self, iterable=[]):
        unit = None

        for i, item in enumerate(iterable):
            if not isinstance(item, self._sub_type):
                raise LnstError("{} only accepts {} objects."
                                .format(self.__class__.__name__,
                                        self._sub_type.__name__))

            if i == 0:
                unit = item.unit

            if item.unit != unit:
                raise LnstError("PerfList items must have the same unit.")

        super(PerfList, self).__init__(iterable)

    def _validate_item(self, item):
        if not isinstance(item, self._sub_type):
            raise LnstError("{} only accepts {} objects."
                            .format(self.__class__.__name__,
                                    self._sub_type.__name__))

        if len(self) > 0 and item.unit != self[0].unit:
            raise LnstError("PerfList items must have the same unit.")

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

class StreamPerf(PerfList, PerfStatMixin):
    _sub_type = PerfInterval

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

class MultiStreamPerf(PerfList, PerfStatMixin):
    _sub_type = StreamPerf

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

class MultiRunPerf(PerfList, PerfStatMixin):
    _sub_type = MultiStreamPerf

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
