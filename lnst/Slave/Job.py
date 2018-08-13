"""
This module defines classes of jobs to be run on a slave

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import os
import re
import sys
import signal
import logging
import multiprocessing
from lnst.Common.JobError import JobError
from lnst.Common.ExecCmd import exec_cmd, ExecCmdFail
from lnst.Common.ConnectionHandler import send_data
from lnst.Common.Logs import log_exc_traceback

def get_job_class(what):
    if what["type"] == "shell":
        return ShellExecJob(what)
    elif what["type"] == "module":
        return ModuleJob(what)
    else:
        logging.error("Unknown job type \"%s\"" % what["type"])
        raise JobError("Unknown command type \"%s\"" % what["type"])

class JobContext(object):
    def __init__(self):
        self._dict = {}

    def add_job(self, job):
        self._dict[job.get_id()] = job

    def del_job(self, job):
        del self._dict[job.get_id()]

    def get_job(self, id):
        if id in self._dict:
            return self._dict[id]
        else:
            return None

    def _kill_all_jobs(self):
        for id in self._dict:
            self._dict[id].kill(sig=signal.SIGKILL)

    def cleanup(self):
        logging.debug("Cleaning up leftover processes.")
        self._kill_all_jobs()
        self._dict = {}

    def get_parent_pipes(self):
        pipes = {}
        for key in self._dict:
            pipe = self._dict[key].get_parent_pipe()
            if pipe != None:
                pipes[key] = pipe
        return pipes

class Job(object):
    def __init__(self, what, log_ctl):
        self._job_cls = get_job_class(what)
        self._what = what

        self._id = what["job_id"]
        self._parent_pipe = None
        self._child_pipe = None
        self._process = None
        self._pid = None
        self._log_ctl = log_ctl
        self._finished = False

    def get_id(self):
        return self._id

    def get_parent_pipe(self):
        return self._parent_pipe

    def run(self):
        self._parent_pipe, self._child_pipe = multiprocessing.Pipe()
        self._process = multiprocessing.Process(target=self._run)

        self._process.daemon = False
        self._process.start()
        self._pid = self._process.pid

        logging.info("Running job %d with pid \"%d\"" % (self._id, self._pid))
        return True

    def _run(self):
        os.setpgrp()
        signal.signal(signal.SIGHUP, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

        self._log_ctl.disable_logging()
        self._log_ctl.set_connection(self._child_pipe)

        result = {}
        try:
            self._job_cls.run()
            job_result = self._job_cls.get_result()
        except Exception as e:
            log_exc_traceback()
            job_result = {}
            job_result["passed"] = False
            job_result["type"] = "exception"
            job_result["res_data"] = self._job_cls.get_result()
            job_result["res_data"]["exception"] = e
        finally:
            result["type"] = "job_finished"
            result["job_id"] = self._id
            result["result"] = job_result

        send_data(self._child_pipe, result)
        self._child_pipe.close()

    def kill(self, sig=signal.SIGKILL):
        if self._finished:
            logging.debug("Job finished before sending the signal")
            return True
        try:
            logging.debug("Sending signal %s to pid %d" % (sig, self._pid))
            os.killpg(self._pid, sig)

            if sig == signal.SIGKILL:
                self.set_finished(dict(type = "job_finished",
                                       job_id = self._id,
                                       result = dict(passed = False,
                                                     res_data = "Job killed",
                                                     type = "result")))

                send_data(self._child_pipe, self.get_result())
            return True
        except OSError as exc:
            logging.error(str(exc))
            return False

    def join(self):
        self._process.join()

    def set_finished(self, result):
        self._finished = True
        self._result = result

    def get_result(self):
        return self._result

class GenericJob(object):
    def __init__(self, what):
        self._what = what
        self._result = {"passed": False,
                        "res_data": None,
                        "type": "result"}

    def run(self):
        raise JobError("Method run must be defined.")

    def get_result(self):
        return self._result

    # def format_res_data(self, res_data, level=0):
        # self._check_res_data(res_data)
        # formatted_data = ""
        # if res_data:
            # max_key_len = 0
            # for key in res_data.keys():
                # if len(key) > max_key_len:
                    # max_key_len = len(key)
            # for key, value in res_data.iteritems():
                # if type(value) == dict:
                    # formatted_data += level*4*" " + str(key) + ":\n"
                    # formatted_data += self.format_res_data(value, level+1)
                # if type(value) == list:
                    # formatted_data += level*4*" " + str(key) + ":\n"
                    # for i in range(0, len(value)):
                        # formatted_data += (level+1)*4*" " +\
                                          # "item %d:" % (i+1) + "\n"
                        # formatted_data += self.format_res_data(value[i],
                                                               # level+2)
                # else:
                    # formatted_data += level*4*" " + str(key) + ":" + \
                                      # (max_key_len-len(key))*" " + \
                                      # "\t" + str(value) + "\n"

        # return formatted_data

    # def _check_res_data(self, res_data):
        # name_start_char = u":A-Z_a-z\xC0-\xD6\xD8-\xF6\xF8-\u02FF"\
                          # u"\u0370-\u037D\u037F-\u1FFF\u200C-\u200D"\
                          # u"\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF"\
                          # u"\uF900-\uFDCF\uFDF0-\uFFFD\U00010000-\U000EFFFF"
        # name_char = name_start_char + u"\-\.0-9\xB7\u0300-\u036F\u203F-\u2040"
        # name = u"[%s]([%s])*$" % (name_start_char, name_char)
        # char_data = u"[^<&]*"
        # if isinstance(res_data, dict):
            # for key in res_data:
                # if not re.match(name, key, re.UNICODE):
                    # msg = "'%s' can't be used as an xml element name!" % key
                    # raise JobError(msg)
                # else:
                    # self._check_res_data(res_data[key])
        # elif isinstance(res_data, list):
            # for i in res_data:
                # self._check_res_data(i)
        # else:
            # try:
                # string = str(res_data)
            # except:
                # msg = "res_data can only contain dictionaries, lists or "\
                      # "stringable objects!"
                # raise JobError(msg)
            # if not re.match(char_data, string, re.UNICODE):
                # msg = "'%s' can't be used as character data in xml!" % string
                # raise JobError(msg)

    # def _format_cmd_res_header(self):
        # if self._what["netns"] != None:
            # netns = "(%s) " % self._what["netns"]
        # else:
            # netns = ""

        # return "%-9s" % (self._what["type"] + netns)

class ShellExecJob(GenericJob):
    def run(self):
        try:
            stdout, stderr = exec_cmd(self._what["command"], self._what["json"])
            self._result["passed"] = True
            self._result["res_data"] = {"stdout": stdout, "stderr": stderr}
        except ExecCmdFail as e:
            self._result["passed"] = False
            self._result["res_data"] = res_data = {"stdout": e.get_stdout(),
                                                   "stderr": e.get_stderr()}

    # def _format_cmd_res_header(self):
        # cmd_type = self._what["type"]
        # cmd_val = self._what["command"]

        # if self._what["netns"] != None:
            # netns = "(%s) " % self._what["netns"]
        # else:
            # netns = ""

        # cmd = "%-9scmd: \"%s\"" %(cmd_type + netns, cmd_val)
        # return cmd

class ModuleJob(GenericJob):
    def run(self):
        try:
            self._result["passed"] = self._what["module"].run()
            self._result["res_data"] = self._what["module"]._get_res_data()
        except Exception as e:
            log_exc_traceback()
            self._result["passed"] = False
            self._result["type"] = "module_exception"
            self._result["res_data"] = {"exception": e}
