"""
Defines the VxlanDevice class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import pyroute2
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.DeviceError import DeviceError, DeviceConfigError
from lnst.Common.IpAddress import ipaddress
from lnst.Devices.Device import Device
from lnst.Devices.SoftDevice import SoftDevice

class VxlanDevice(SoftDevice):
    _name_template = "t_vxlan"
    _link_type = "vxlan"

    _linkinfo_data_map = {"vxlan_id": "IFLA_VXLAN_ID",
                          "dst_port": "IFLA_VXLAN_PORT",
                          "realdev": "IFLA_VXLAN_LINK",
                          "group_ip": "IFLA_VXLAN_GROUP",
                          "remote_ip": "IFLA_VXLAN_GROUP"}

    def __init__(self, ifmanager, *args, **kwargs):
        try:
            kwargs["vxlan_id"] = int(kwargs["vxlan_id"])
        except:
            raise DeviceConfigError("Invalid value for vxlan_id argument.")

        if "realdev" in kwargs:
            if not isinstance(kwargs["realdev"], Device):
                raise DeviceConfigError("Invalid value for realdev argument.")

            kwargs["realdev"] = kwargs["realdev"].ifindex

        if "group_ip" in kwargs and "remote_ip" in kwargs:
            raise DeviceError("group and remote cannot both be specified for vxlan")

        if "group_ip" in kwargs:
            kwargs["group_ip"] = str(ipaddress(kwargs.get("group_ip")))
        elif "remote_ip" in kwargs:
            kwargs["remote_ip"] = str(ipaddress(kwargs.get("remote_ip")))
        else:
            raise DeviceError("group or remote must be specified for vxlan")

        try:
            kwargs["dst_port"] = int(kwargs.get("dst_port",0))
        except:
            raise DeviceConfigError("Invalid value for dst_port argument.")

        super(VxlanDevice, self).__init__(ifmanager, *args, **kwargs)

    # @property
    # def real_dev(self):
        # return self._real_dev

    # @property
    # def vxlan_id(self):
        # return self._vxlan_id

    # @property
    # def group_ip(self):
        # return self._group_ip

    # @property
    # def remote_ip(self):
        # return self._remote_ip

    # @property
    # def dst_port(self):
        # return self._dst_port
