"""
Defines the MacvlanDevice class

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Common.DeviceError import DeviceConfigError
from lnst.Devices.Device import Device
from lnst.Devices.SoftDevice import SoftDevice

class MacvlanDevice(SoftDevice):
    _name_template = "t_macvlan"
    _link_type = "macvlan"

    _mandatory_opts = ["realdev"]

    @property
    def realdev(self):
        idx = self._nl_msg.get_attr("IFLA_LINK")
        return self._if_manager.get_device(idx)

    @realdev.setter
    def realdev(self, val):
        if not isinstance(val, Device):
            raise DeviceConfigError("Value must be a Device object.")

        self._update_attr(val.ifindex, "IFLA_LINK")
        self._nl_link_sync("set")

    @property
    def mode(self):
        return str(self._get_linkinfo_data_attr("IFLA_MACVLAN_MODE"))

    @mode.setter
    def mode(self, val):
        self._set_linkinfo_data_attr("IFLA_MACVLAN_MODE", str(val))
        self._nl_link_sync("set")
