"""
Defines the MacvlanDevice class

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

class MacvlanDevice(SoftDevice):
    _name_template = "t_macvlan"
    _link_type = "macvlan"

    _link_map = dict(SoftDevice._link_map)
    _link_map.update({"realdev": "IFLA_LINK"})

    _linkinfo_data_map = {"mode": "IFLA_MACVLAN_MODE"}

    def __init__(self, ifmanager, *args, **kwargs):
        if not isinstance(kwargs["realdev"], Device):
            raise DeviceConfigError("Invalid value for realdev argument.")

        kwargs["realdev"] = kwargs["realdev"].ifindex

        super(MacvlanDevice, self).__init__(ifmanager, *args, **kwargs)
