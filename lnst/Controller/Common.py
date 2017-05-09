"""
Common Controller module. At the moment it only defines the ControllerError
exception class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import os
import sys
from lnst.Common.LnstError import LnstError

class ControllerError(LnstError):
    pass
