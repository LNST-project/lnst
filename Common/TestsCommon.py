"""
This module defines common test stuff

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import re
import logging
import sys
import os
import signal
from NetTest.NetTestCommand import NetTestCommandGeneric

class testLogger(logging.Logger):
    def __init__(self, name, level=logging.NOTSET):
        logging.Logger.__init__(self, name, level)

    def findCaller(self):
        """
        Find the stack frame of the caller so that we can note the source
        file name, line number and function name.
        """
        f = logging.currentframe()
        #On some versions of IronPython, currentframe() returns None if
        #IronPython isn't run with -X:Frames.
        if f is not None:
            f = f.f_back.f_back
        rv = "(unknown file)", 0, "(unknown function)"
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            if filename == logging._srcfile:
                f = f.f_back.f_back
                continue
            rv = (filename, f.f_lineno, co.co_name)
            break
        return rv

logging._acquireLock()
try:
    logging.setLoggerClass(testLogger)
    logging.getLogger("root.testLogger")
    logging.setLoggerClass(logging.Logger)
finally:
    logging._releaseLock()

class TestOptionMissing(Exception):
    pass

class TestGeneric(NetTestCommandGeneric):
    def __init__(self, command):
        self._testLogger = logging.getLogger("root.testLogger")
        self._read_pipe, self._write_pipe = os.pipe()
        signal.signal(signal.SIGINT, self._signal_intr_handler)
        NetTestCommandGeneric.__init__(self, command)

    def __del__(self):
        os.close(self._read_pipe)
        os.close(self._write_pipe)

    def _signal_intr_handler(self, signum, frame):
        os.write(self._write_pipe, "a")
    
    def wait_on_interrupt(self):
        '''
        Should be used by test implementation for waiting on SIGINT
        '''
        while True:
            try:
                os.read(self._read_pipe, 1)
            except OSError:
                continue
            break

    def set_fail(self, err_msg, res_data = None):
        self._testLogger.error("FAILED - %s" % err_msg)
        res = {"passed": False, "err_msg": err_msg}
        if res_data:
            res["res_data"] = res_data
        self.set_result(res)
        return res

    def set_pass(self, res_data = None):
        self._testLogger.debug("PASSED")
        res = {"passed": True}
        if res_data:
            res["res_data"] = res_data
        self.set_result(res)
        return res

    def _get_val(self, value, opt_type, default):
        if opt_type == "addr":
            '''
            If address type is specified do "slashcut"
            '''
            return re.sub(r'/.*', r'', value)

        if default != None:
            '''
            In case a default value is passed, retype value
            by the default value type.
            '''
            return (type(default))(value)

        return value

    def get_opt(self, name, multi=False, mandatory=False, opt_type="", default=None):
        try:
            option = self._command["options"][name]
        except KeyError:
            if mandatory:
                raise TestOptionMissing
            if multi:
                return [default]
            else:
                return default

        if multi:
            value = []
            for op in option:
                value.append(self._get_val(op["value"], opt_type, default))
        else:
            value = self._get_val(option[0]["value"], opt_type, default)

        return value

    def get_mopt(self, name, opt_type=""):
        '''
        This should be used to get mandatory options
        '''
        return self.get_opt(name, mandatory=True, opt_type=opt_type)

    def get_multi_opt(self, name, mandatory=False, opt_type="", default=None):
        '''
        This should be used to get multi options (array of values)
        '''
        return self.get_opt(name, multi=True, mandatory=mandatory,
                            opt_type=opt_type, default=default)

    def get_multi_mopt(self, name, opt_type=""):
        '''
        This should be used to get mandatory multi options (array of values)
        '''
        return self.get_multi_opt(name, mandatory=True, opt_type=opt_type)
