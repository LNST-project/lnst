"""
Defines the SoftDevice class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Common.ExecCmd import exec_cmd
from lnst.Common.DeviceError import DeviceError
from lnst.Devices.Device import Device

class SoftDevice(Device):
    _name_template = "soft_dev"

    _modulename = ""
    _moduleparams = ""
    _type_initialized = False

    def __init__(self, ifmanager, *args, **kwargs):
        super(SoftDevice, self).__init__(ifmanager)

        self._name = kwargs.get("name", None)
        if self._name is None:
            self._name = ifmanager.assign_name(self._name_template)

        self._type_init()

    @classmethod
    def _type_init(cls):
        if cls._modulename and not cls._type_initialized:
            exec_cmd("modprobe %s %s" % (cls._modulename, cls._moduleparams))
            cls._type_initialized = True

    @property
    def name(self):
        try:
            return super(SoftDevice, self).name
        except:
            return self._name

    def _create(self):
        #TODO virtual method
        msg = "Classes derived from SoftDevice MUST define a create method."
        raise DeviceError(msg)

    def _destroy(self):
        exec_cmd("ip link del dev %s" % self.name)
