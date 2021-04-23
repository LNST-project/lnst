"""
Defines the NetNamespace class that represents the API for a network namespace
of a slave machine.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import logging
from lnst.Devices.VirtualDevice import VirtualDevice
from lnst.Devices.RemoteDevice import RemoteDevice
from lnst.Controller.Namespace import Namespace
from lnst.Controller.Namespace import HostError

class NetNamespace(Namespace):
    """Namespace derived class for a network namespace

    Created by the tester, should be assigned to a Host object which will
    perform the namespace creation. After that the tester uses it the same
    way."""
    def __init__(self, name):
        super(NetNamespace, self).__init__(None)

        self._name = name
        #self.jobs = None #TODO
