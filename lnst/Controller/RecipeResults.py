"""
This module defines classes for storing Result data related to a test run.
Most are generated automatically by LNST during test execution and a tester
also has a Recipe interface available to create Result objects for custom
entries.

Copyright 2018 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import logging
import time
from enum import IntEnum
from typing import Optional, Union

class ResultLevel(IntEnum):
    IMPORTANT = 1
    NORMAL = 2
    DEBUG = 3


class ResultType(IntEnum):
    FAIL = 0  # fail is evaluated as zero to keep compatibility with evaluators that use False == test fail
    PASS = 1
    WARNING = 2

    def __str__(self):
        if self == ResultType.FAIL:
            return "FAIL"
        elif self == ResultType.PASS:
            return "PASS"
        else:
            return "WARNING"

    @staticmethod
    def max_severity(first, second):
        severity = [ResultType.FAIL, ResultType.WARNING, ResultType.PASS]

        for level in severity:
            if first == level or second == level:
                return level

        return ResultType.PASS

    def __bool__(self):
        # method implemented due to compatibility reasons
        if self == ResultType.FAIL:
            return False

        return True


class BaseResult(object):
    """Base class for storing result data

    should not be instantiated directly, only defines the interface"""
    def __init__(self, result: ResultType = ResultType.PASS):
        if not isinstance(result, ResultType):  # backwards compatibility
            result = ResultType(result)
            logging.warning("Please use ResultType for job results instead of boolean value")

        self._timestamp = time.time()
        self._result = result

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def result(self):
        return self._result

    @result.setter
    def result(self, value: ResultType):
        self._result = value

    @property
    def description(self):
        return "Short description of result if relevant"

    @property
    def data(self):
        return None

    @property
    def level(self):
        return ResultLevel.DEBUG

    @property
    def data_level(self):
        return ResultLevel.DEBUG

class JobResult(BaseResult):
    """Base class for storing result data of Jobs

    should not be instantiated directly, just stores the Job instance"""
    def __init__(self, job, result):
        super(JobResult, self).__init__(result)

        self._job = job

    @property
    def job(self):
        return self._job

    @property
    def level(self):
        return self.job.level

    @property
    def data_level(self):
        return self.job.level+1

class JobStartResult(JobResult):
    """Generated automatically when a Job is successfully started on an agent"""
    @property
    def description(self):
        return "Job started: {}".format(str(self.job))

class JobFinishResult(JobResult):
    """Generated automatically when a Job is finished on an agent

    success depends on the Job passed value and returns the data returned as
    a result of the Job."""
    def __init__(self, job):
        super(JobFinishResult, self).__init__(job, ResultType.FAIL)  # there is overridden .result method anyway

    @property
    def success(self):
        return self._job.passed

    @property
    def result(self):
        return self._job.passed

    @property
    def description(self):
        return "Job finished: {}".format(str(self.job))

    @property
    def data(self):
        return self.job.result


class DeviceConfigResult(BaseResult):
    def __init__(self, result, device):
        super(DeviceConfigResult, self).__init__(result)
        self._device = device

    @property
    def level(self):
        return ResultLevel.NORMAL

    @property
    def device(self):
        return self._device


class DeviceCreateResult(DeviceConfigResult):
    @property
    def description(self):
        dev_clsname = self.device._dev_cls.__name__
        dev_args = self.device._dev_args
        dev_kwargs = self.device._dev_kwargs

        return "Creating Device {hostid}{netns}.{dev_id} = {cls_name}({args}{comma}{kwargs})".format(
            hostid=self.device.host.hostid,
            netns=".{}".format(self.device.netns.name)
            if self.device.netns and self.device.netns.name
            else "",
            dev_id=self.device._id,
            cls_name=dev_clsname,
            args=", ".join([repr(arg) for arg in dev_args]),
            comma=", " if dev_args and dev_kwargs else "",
            kwargs=", ".join(
                ["{}={}".format(k, repr(v)) for k, v in dev_kwargs.items()]
            ),
        )


class DeviceMethodCallResult(DeviceConfigResult):
    def __init__(self, result, device, method_name, args, kwargs):
        super(DeviceMethodCallResult, self).__init__(result, device)
        self._method_name = method_name
        self._args = args
        self._kwargs = kwargs

    @property
    def method_name(self):
        return self._method_name

    @property
    def args(self):
        return self._args

    @property
    def kwargs(self):
        return self._kwargs

    @property
    def description(self):
        return "Calling Device method {host}{netns}.{dev_id}.{fname}({args}{comma}{kwargs})".format(
            host=self.device.host.hostid,
            netns=(
                ".{}".format(self.device.netns.name)
                if self.device.netns and self.device.netns.name
                else ""
            ),
            dev_id=self.device._id,
            fname=self.method_name,
            args=", ".join([repr(arg) for arg in self.args]),
            comma=", " if self.args and self.kwargs else "",
            kwargs=", ".join(
                ["{}={}".format(k, repr(v)) for k, v in self.kwargs.items()]
            ),
        )


class DeviceAttrSetResult(DeviceConfigResult):
    def __init__(self, result, device, attr_name, value, old_value):
        super(DeviceAttrSetResult, self).__init__(result, device)
        self._attr_name = attr_name
        self._value = value
        self._old_value = old_value

    @property
    def attr_name(self):
        return self._attr_name

    @property
    def value(self):
        return self._value

    @property
    def old_value(self):
        return self._old_value

    @property
    def description(self):
        return "Setting Device attribute {host}{netns}.{dev_id}.{attr} = {val}, previous value = {old_val}".format(
            host=self.device.host.hostid,
            netns=(
                ".{}".format(self.device.netns.name)
                if self.device.netns and self.device.netns.name
                else ""
            ),
            dev_id=self.device._id,
            attr=self.attr_name,
            val=self.value,
            old_val=self.old_value,
        )


class Result(BaseResult):
    """Class intended to store aribitrary tester supplied data

    Will be created when the tester calls the Recipe interface for adding
    results."""
    def __init__(self, result, description="", data=None,
                 level=None, data_level=None):
        super(Result, self).__init__(result)

        self._description = description
        self._data = data
        self._level = (level
                if isinstance(level, ResultLevel)
                else ResultLevel.IMPORTANT)
        self._data_level = (data_level
                if isinstance(data_level, ResultLevel)
                else ResultLevel.IMPORTANT+1)

    @property
    def description(self):
        return self._description

    @property
    def data(self):
        return self._data

    @property
    def level(self):
        return self._level

    @property
    def data_level(self):
        return self._data_level


class MeasurementResult(Result):
    def __init__(
        self,
        measurement_type: str,
        result: Union[ResultType, bool] = ResultType.PASS,
        description: str = "",
        data: Optional[dict] = None,
    ):
        self._measurement_type = measurement_type
        super().__init__(
            result,
            description,
            data=data or {},
        )

    @property
    def measurement_type(self) -> str:
        return self._measurement_type
