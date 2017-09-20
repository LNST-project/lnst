"""
Defines the MasterDevice class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Devices.SoftDevice import SoftDevice

class MasterDevice(SoftDevice):
    """Common class for all master device types

    Implements the slaves attribute getter and the slave_{add, del} methods.
    """
    @property
    def slaves(self):
        ret = []

        for dev in self._if_manager.get_devices():
            if dev.master is self:
                ret.append(dev)
        return ret

    def slave_add(self, dev):
        dev.master = self

    def slave_del(self, dev):
        dev.master = None
