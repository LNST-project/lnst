"""
This module defines exec_cmd useful for running commands

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import logging
import subprocess
from lnst.Common.LnstError import LnstError

class ExecCmdFail(LnstError):
    _cmd = None
    _retval = None
    _stderr = None
    _stdout = None
    _report_stderr = None

    def __init__(self, cmd=None, retval=None, outs=["", ""], report_stderr=False):
        self._cmd = cmd
        self._stdout = outs[0]
        self._stderr = outs[1]
        self._retval = retval
        self._report_stderr = report_stderr

    def get_cmd(self):
        return self._cmd

    def get_stderr(self):
        return self._stderr

    def get_stdout(self):
        return self._stdout

    def get_retval(self):
        return self._retval

    def __str__(self):
        retval = ""
        stderr = ""
        if self._retval:
            retval = " (exited with %d)" % self._retval
        if self._report_stderr:
            stderr = " [%s]" % self._stderr
        return "Command \"%s\" execution failed%s%s" % (self._cmd, retval, stderr)

def log_output(log_func, out_type, out):
    log_func("%s:\n"
             "----------------------------\n"
             "%s"
             "----------------------------"
             % (out_type, out))

def exec_cmd(cmd, die_on_err=True, log_outputs=True, report_stderr=False, json=False, stdin=None):
    cmd = cmd.rstrip(" ")
    logging.debug("Executing: \"%s\"" % cmd)
    subp = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, stdin=subprocess.PIPE,
                            close_fds=True)
    (data_stdout, data_stderr) = subp.communicate(input = stdin)
    data_stdout = data_stdout.decode()
    data_stderr = data_stderr.decode()

    '''
    When we should not die on error, do not print anything and let
    the caller to decide what to do.
    '''
    if log_outputs:
        if data_stdout:
            log_output(logging.debug, "Stdout", data_stdout)
        if data_stderr:
            log_output(logging.debug, "Stderr", data_stderr)
    if subp.returncode and die_on_err:
        err = ExecCmdFail(cmd, subp.returncode, [data_stdout, data_stderr], report_stderr)
        logging.error(err)
        raise err

    if json:
        import json
        data_stdout = json.loads(data_stdout)

    return data_stdout, data_stderr
