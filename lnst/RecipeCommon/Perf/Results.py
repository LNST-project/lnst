from lnst.Common.LnstError import LnstError
from lnst.Common.Utils import std_deviation

class EmptySlice(LnstError):
    pass

class PerfStatMixin(object):
    @property
    def average(self):
        try:
            return float(self.value) / self.duration
        except ZeroDivisionError:
            return float('inf') if self.value >= 0 else float('-inf')

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

    @property
    def start_timestamp(self):
        raise NotImplementedError()

    @property
    def end_timestamp(self):
        raise NotImplementedError()

    def time_slice(self, start, end):
        raise NotImplementedError()

class PerfInterval(PerfResult):
    def __init__(self, value, duration, unit, timestamp):
        self._value = value
        self._duration = duration
        self._unit = unit
        self._timestamp = timestamp

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
    def start_timestamp(self):
        return self._timestamp

    @property
    def end_timestamp(self):
        return self._timestamp + self.duration

    @property
    def std_deviation(self):
        return 0

    def __str__(self):
        return "{:.2f} {} in {:.2f} seconds".format(
                float(self.value), self.unit, float(self.duration))

    def time_slice(self, start, end):
        if end <= self.start_timestamp or start >= self.end_timestamp:
            raise EmptySlice(
                "current start, end {} {}; request start, end {}, {}".format(
                    self.start_timestamp, self.end_timestamp, start, end,
                )
            )

        new_start = max(self.start_timestamp, start)
        new_end = min(self.end_timestamp, end)
        new_duration = new_end - new_start
        new_value = self.value * (new_duration/self.duration)
        return PerfInterval(new_value, new_duration, self.unit, new_start)

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
        if isinstance(item, list):
            if not isinstance(i, slice):
                raise LnstError("{} accepts list values in slice assignment "
                    "only".format(self.__class__.__name__))

            for j in item:
                self._validate_item(j)
        else:
            self._validate_item(item)

        super(PerfList, self).__setitem__(i, item)

    def time_slice(self, start, end):
        result = self.__class__()
        for item in self:
            try:
                item_slice = item.time_slice(start, end)
                result.append(item_slice)
            except EmptySlice:
                continue
        if len(result) == 0:
            raise EmptySlice(
                "current start, end {} {}; request start, end {}, {}".format(
                    self.start_timestamp, self.end_timestamp, start, end,
                )
            )
        return result

class SequentialPerfResult(PerfList, PerfResult):
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

    @property
    def start_timestamp(self):
        return self[0].start_timestamp

    @property
    def end_timestamp(self):
        return self[-1].end_timestamp

class ParallelPerfResult(PerfList, PerfResult):
    @property
    def value(self):
        return sum([i.value for i in self])

    @property
    def duration(self):
        min_start = min([item.start_timestamp for item in self])
        max_end = max([item.end_timestamp for item in self])
        return max_end - min_start

    @property
    def unit(self):
        if len(self) > 0:
            return self[0].unit
        else:
            return None

    @property
    def start_timestamp(self):
        return min([i.start_timestamp for i in self])

    @property
    def end_timestamp(self):
        return max([i.end_timestamp for i in self])

def result_averages_difference(a, b):
    if a is None or b is None:
        return None
    return ((a.average / b.average) * 100) - 100
