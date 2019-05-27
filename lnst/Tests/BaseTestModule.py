"""
Defines the BaseTestModule class and the TestModuleError exception.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import time
import copy
import signal
from lnst.Common.Parameters import Parameters, Param
from lnst.Common.LnstError import LnstError

from lnst.Common.Logs import log_exc_traceback

class TestModuleError(LnstError):
    """Exception used by BaseTestModule and derived classes"""
    pass

class InterruptException(TestModuleError):
    """Exception used to handle SIGINT waiting"""
    pass

class BaseTestModule(object):
    """Base class for test modules

    All user defined testmodule classes should inherit from this class. The
    class itself defines the interface for a test module that is required by
    LNST - the virtual run method.

    It also implements the __init__ method that should be called by the derived
    classes as it implements Parameter checking.

    Derived classes can define test parameters by assigning 'Param' instances
    to class attributes, these will be parsed during initialization (this
    includes type checking and checks for mandatory parameters) and provided
    through the self.params object in the BaseTestModule object instance (for
    use during test execution) e.g.:

    class MyTest(BaseTestModule):
        int_param = IntParam(mandatory=True)
        optional_param = IntParam()
        def run(self):
            x = self.params.int_param
            if "optional_param" in self.params:
                x += self.params.optional_param

    MyTest(int_param=2, optional_param=3)
    """
    def __init__(self, **kwargs):
        """
        Args:
            kwargs -- dictionary of arbitrary named arguments that correspond
                to class attributes (Param type). Values will be parsed and
                set to Param instances under the self.params object.
        """
        #by defaults loads the params into self.params - no checks pseudocode:
        self.params = Parameters()

        for name in dir(self):
            param = getattr(self, name)
            if isinstance(param, Param):
                if name in kwargs:
                    val = kwargs.pop(name)
                    val = param.type_check(val)
                    setattr(self.params, name, val)
                else:
                    try:
                        val = copy.deepcopy(param.default)
                        setattr(self.params, name, val)
                    except AttributeError:
                        if param.mandatory:
                            raise TestModuleError("Parameter {} is mandatory"
                                                  .format(name))

        if len(kwargs):
            for name in list(kwargs.keys()):
                raise TestModuleError("Unknown parameter {}".format(name))

        self._res_data = None

    def run(self):
        raise NotImplementedError("Method 'run' MUST be defined")

    def wait_for_interrupt(self):
        def handler(signum, frame):
            raise InterruptException()

        try:
            old_handler = signal.signal(signal.SIGINT, handler)
            signal.pause()
        except InterruptException:
            pass
        finally:
            signal.signal(signal.SIGINT, old_handler)

    def _get_res_data(self):
        return self._res_data
