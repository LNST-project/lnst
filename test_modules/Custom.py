"""
This module defines custom test

Copyright 2016 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jiri@mellanox.com (Jiri Pirko)
"""

from lnst.Common.TestsCommon import TestGeneric
from lnst.Common.Utils import bool_it

class Custom(TestGeneric):
    def run(self):
        fail_str = self.get_opt("fail")
        if not fail_str:
            fail = False
        else:
            fail = bool_it(fail_str)

        res_data = self.get_single_opts()
        if "fail" in res_data:
            del(res_data["fail"])

        if fail:
            return self.set_fail(res_data)

        return self.set_pass(res_data)
