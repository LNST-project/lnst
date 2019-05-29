"""
Defines the Job class, representing the tester facing API for manipulating
remotely running tasks.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import logging
import signal
from lnst.Common.JobError import JobError
from lnst.Common.NetTestCommand import DEFAULT_TIMEOUT
from lnst.Tests.BaseTestModule import BaseTestModule
from lnst.Controller.RecipeResults import ResultLevel

class Job(object):
    """Tester facing Job API

    Objects of this class are created when a tester calls the 'run' method of
    a Host object. A Job object can represent both a remotely running task (a
    background job) or a remote task that already finished.
    Example:
        job = m1.run("ls ~/")
        print job.stdout
    """
    def __init__(self, namespace, what,
                 expect=True, json=False, desc=None,
                 level=ResultLevel.DEBUG):
        self._what = what
        self._expect = expect
        self._json = json
        self._netns = namespace
        self._desc = desc
        self._level = level

        self._res = None

        if self.type == "unknown":
            raise JobError("Unable to run '%s'" % str(what))

        self._id = None

    @property
    def id(self):
        """id of the job

        Used internally by the Machine class to identify results coming
        from the slave.
        TODO make private?
        """
        return self._id

    @id.setter
    def id(self, val):
        if self._id is not None:
            raise Exception("Id already set")
        self._id = val

    @property
    def what(self):
        return self._what

    @property
    def type(self):
        if isinstance(self.what, BaseTestModule):
            return "module"
        elif isinstance(self.what, str):
            return "shell"
        return "unknown"

    @property
    def host(self):
        """the initial namespace of the host the job is running on"""
        return self._netns.initns

    @property
    def netns(self):
        """network namespace the Job is running in"""
        return self._netns

    @property
    def stdout(self):
        """standard output of the Job

        Type: string
        Only applicable for Jobs running a shell command
        """
        try:
            return self._res["res_data"]["stdout"]
        except:
            return ""

    @property
    def stderr(self):
        """standard error output of the Job

        Type: string
        Only applicable for Jobs running a shell command
        """
        try:
            return self._res["res_data"]["stderr"]
        except:
            return ""

    @property
    def result(self):
        """result of the Job

        Type:
            depends on the type of the job. For python modules it is whatever
            the module sets as the _res_data attribute.
            For shell commands it is a dictionary with stdout and stderr.
        """
        try:
            return self._res["res_data"]
        except:
            return None

    @property
    def level(self):
        return self._level

    @level.setter
    def level(self, value):
        self._level = value

    @property
    def passed(self):
        """Indicates whether or not the Job passed

        The return value is True or False based on if the Job was expected to
        pass or fail.

        Type: Boolean
        """
        try:
            return self._res["passed"] == self._expect
        except:
            return False

    @property
    def finished(self):
        """Indicates whether or not the Job finished running

        Type: Boolean
        """
        if self._res is not None:
            return True
        else:
            return False

    def start(self, bg=False, timeout=DEFAULT_TIMEOUT):
        self._netns._machine.run_job(self)

        if not bg:
            if not self.wait(timeout):
                logging.debug("Killing timed-out job")
                self.kill()
        return self

    def wait(self, timeout=DEFAULT_TIMEOUT):
        """waits for the Job to finish for the specified amount of time

        Args:
            timeout -- integer value indicating how long to wait for.
                Default is DEFAULT_TIMEOUT.
                Use zero to wait forever. Don't use for infinitelly running
                jobs...
                If non-zero LNST uses a timed SIGALARM signal to return from
                this method.
        Returns:
            True if the Job finished, False if the Job is still running and
            the wait method just timed out.
        """
        if self.finished:
            return True
        if timeout < 0:
            raise JobError("Negative timeout value not allowed.")
        return self._netns._machine.wait_for_job(self, timeout)

    def kill(self, signal=signal.SIGKILL):
        """send specified signal to the remotely running Job process

        Args:
            signal -- integer value of the signal to be sent
                Default is SIGKILL
        Returns:
            True if the Job finished before the signal was sent or if the
                signal was sent successfully.
            False if an exception was raised while sending the signal.
        """
        if self.finished:
            logging.info("Job {} on host {} already finished, skipping kill call."
                    .format(self._id, self._netns.hostid))
            return True

        logging.info("Sending signal {} to job {} on host {}".format(signal,
                     self._id, self._netns.hostid))
        return self._netns._machine.kill(self, signal)

    def _to_dict(self):
        d = {"job_id": self._id,
             "type": self.type,
             "json": self._json}
        if self.type == "shell":
            d["command"] = self._what
        elif self.type == "module":
            d["module"] = self._what
        else:
            raise JobError("Unknown Job type %s" % self.type)
        return d

    def __str__(self):
        attrs = ["type(%s)" % self.type]

        if self._netns is not None:
            attrs.append("netns(%s)" % self._netns.name)

        if not self._expect:
            attrs.append("expecting FAIL")

        attrs.append(repr(self._what))

        return ", ".join(attrs)
