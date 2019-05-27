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

import time
from enum import IntEnum

class ResultLevel(IntEnum):
    IMPORTANT = 1
    NORMAL = 2
    DEBUG = 3

class BaseResult(object):
    """Base class for storing result data

    should not be instantiated directly, only defines the interface"""
    def __init__(self, success=True):
        self._timestamp = time.time()
        self._success = success

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def success(self):
        return self._success

    @success.setter
    def success(self, value):
        self._success = value

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
    def __init__(self, job, success):
        super(JobResult, self).__init__(success)

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
    """Generated automatically when a Job is succesfully started on a slave"""
    @property
    def description(self):
        return "Job started: {}".format(str(self.job))

class JobFinishResult(JobResult):
    """Generated automatically when a Job is finished on a slave

    success depends on the Job passed value and returns the data returned as
    a result of the Job."""
    def __init__(self, job):
        super(JobFinishResult, self).__init__(job, None)

    @property
    def success(self):
        return self._job.passed

    @property
    def description(self):
        return "Job finished: {}".format(str(self.job))

    @property
    def data(self):
        return self.job.result

class Result(BaseResult):
    """Class intended to store aribitrary tester supplied data

    Will be created when the tester calls the Recipe interface for adding
    results."""
    def __init__(self, success, description="", data=None,
                 level=None, data_level=None):
        super(Result, self).__init__(success)

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
