"""
Defines the Devices class which iterates over Device objects tracked by the
device database of a Machine object.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Devices.Device import Device

class Devices(object):
    def __init__(self, host):
        self._host = host

    def __iter__(self):
        for x in self._host._device_database.values():
            if isinstance(x, Device):
                yield x
