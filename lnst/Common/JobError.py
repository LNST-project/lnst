"""
This module defines the common JobError exception used by both the Controller
and the Agent

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Common.LnstError import LnstError

class JobError(LnstError):
    """Base class for client errors."""
    def __init__(self, s):
        self._s = s

    def __str__(self):
        return "JobError: " + str(self._s)
