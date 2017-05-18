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
from lnst.Common.TestModule import BaseTestModule

class Job(object):
    """Tester facing Job API

    Objects of this class are created when a tester calls the 'run' method of
    a Host object. A Job object can represent both a remotely running task (a
    background job) or a remote task that already finished.
    Example:
        job = m1.run("ls ~/")
        print job.stdout
    """
    def __init__(self, host, what,
                 expect=True, json=False, netns=None, desc=None):
        self._host = host
        self._what = what
        self._expect = expect
        self._json = json
        self._netns = netns
        self._desc = desc

        self._res = None

        if isinstance(what, BaseTestModule):
            self._type = "module"
        elif type(what) == str:
            self._type = "shell"
        else:
            raise JobError("Unable to run '%s'" % str(what))

        self._id = None

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
    def passed(self):
        """Indicates whether or not the Job passed

        Type: Boolean
        """
        try:
            return self._res["passed"]
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

    @property
    def netns(self):
        """name of the network namespace the Job is running in

        Not relevant yet as network namespaces aren't supported yet.
        """
        if self._cmd is not None:
            return self._cmd["netns"]
        else:
            return None

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

    def wait(self, timeout=0):
        """waits for the Job to finish for the specified amount of time

        Args:
            timeout -- integer value indicating how long to wait for.
                Default is 0, means wait forever. Don't use for infinitelly
                running Jobs.
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
        return self._host.wait_for_job(self, timeout)

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
        logging.info("Sending signal {} to job {} on host {}".format(signal,
                     self._id, self._host.get_id()))
        return self._host.kill(self, signal)

    def _to_dict(self):
        d = {"job_id": self._id,
             "type": self._type,
             "json": self._json}
        if self._type == "shell":
            d["command"] = self._what
        elif self._type == "module":
            d["module"] = self._what
        else:
            raise JobError("Unknown Job type %s" % self._type)
        return d

    def __str__(self):
        attrs = ["type(%s)" % self._type]

        if self._type == "module":
            attrs.append("module(%s)" % self._what.__class__.__name__)
        elif self._type == "shell":
            attrs.append("command(%s)" % self._what)

        if self._netns is not None:
            attrs.append("netns(%s)" % self._netns)

        if not self._expect:
            attrs.append("expecting FAIL")

        return ", ".join(attrs)
