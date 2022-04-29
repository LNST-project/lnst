"""
Defines the LoopbackDevice class.

Copyright 2021 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jtluka@redhat.com (Jan Tluka)
"""

import logging
from lnst.Devices.Device import Device

class LoopbackDevice(Device):
    @Device.name.getter
    def name(self):
        return "lo"

    def _create(self):
        pass

    def down(self):
        logging.warning("Link down operation on LoopbackDevice disallowed")
