"""
Defines the VlanDevice class

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Common.ExecCmd import exec_cmd
from lnst.Devices.SoftDevice import SoftDevice

class VlanDevice(SoftDevice):
    _name_template = "t_vlan"

    def __init__(self, ifmanager, *args, **kwargs):
        super(VlanDevice, self).__init__(ifmanager, args, kwargs)

        self._real_dev = kwargs["real_dev"]
        self._vlan_id = int(kwargs["vlan_id"])

    @property
    def real_dev(self):
        return self._real_dev

    @property
    def vlan_id(self):
        return self._vlan_id

    def _create(self):
        exec_cmd("ip link add link %s %s type vlan id %d" %\
                 (self.real_dev.name, self.name, self.vlan_id))
