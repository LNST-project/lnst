"""
Defines the LnstError exception class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

class LnstError(Exception):
    """Base LNST Exception type

    All LNST related Exceptions should inherit from this class.
    """
    pass
