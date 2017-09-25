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

    _link_map = dict(SoftDevice._link_map)
    _link_map.update({"realdev": "IFLA_LINK"})

    _linkinfo_data_map = {"vlan_id": "IFLA_VLAN_ID"}

    def __init__(self, ifmanager, *args, **kwargs):
        if not isinstance(kwargs["realdev"], Device):
            raise DeviceConfigError("Invalid value for realdev argument.")

        kwargs["realdev"] = kwargs["realdev"].ifindex

        try:
            kwargs["vlan_id"] = int(kwargs["vlan_id"])
        except ValueError:
            raise DeviceConfigError("Invalid value for vlan_id argument.")

        super(VlanDevice, self).__init__(ifmanager, *args, **kwargs)

    @property
    def real_dev(self):
        if self._nl_msg is None:
            return None

        if_id = self._nl_msg.get_attr("IFLA_LINK")
        return self._if_manager.get_device(if_id)

    @property
    def vlan_id(self):
        if self._nl_msg is None:
            return None

        linkinfo = self._nl_msg.get_attr("IFLA_LINKINFO")
        infodata = linkinfo.getattr("IFLA_INFO_DATA")
        return infodata.getattr("IFLA_VLAN_ID")
