"""
Package for all LNST Test classes. It will contain all Test classes provided
and maintained by the LNST upstream and later it will also import test classes
based on user configured directories (from lnst-ctl.conf).

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Tests.IcmpPing import IcmpPing

#TODO add support for test classes from lnst-ctl.conf
