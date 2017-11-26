"""
Defines the VlanDevice class

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import pyroute2
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.DeviceError import DeviceConfigError
from lnst.Devices.Device import Device
from lnst.Devices.SoftDevice import SoftDevice

class VlanDevice(SoftDevice):
    _name_template = "t_vlan"
    _link_type = "vlan"

    _mandatory_opts = ["realdev", "vlan_id"]

    @property
    def realdev(self):
        if self._nl_msg is None:
            return None

        if_id = self._nl_msg.get_attr("IFLA_LINK")
        return self._if_manager.get_device(if_id)

    @realdev.setter
    def realdev(self, val):
        if not isinstance(val, Device):
            raise DeviceConfigError("realdev value must be a Device object.")

        self._update_attr(val.ifindex, "IFLA_LINK")
        self._nl_sync("set")

    @property
    def vlan_id(self):
        try:
            return int(self._get_linkinfo_data_attr("IFLA_VLAN_ID"))
        except:
            return None

    @vlan_id.setter
    def vlan_id(self, val):
        if int(val) < 1 or int(val) > 4095:
            raise DeviceConfigError("Invalid value, must be 1-4095.")

        self._set_linkinfo_data_attr("IFLA_VLAN_ID", int(val))
        self._nl_sync("set")
