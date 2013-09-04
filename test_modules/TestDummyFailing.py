"""
This module defines dummy failing test

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import logging
from lnst.Common.TestsCommon import TestGeneric

class TestDummyFailing(TestGeneric):
    def run(self):
        res_data = {"msg": "what else did you expect?"}
        return self.set_fail(res_data)
