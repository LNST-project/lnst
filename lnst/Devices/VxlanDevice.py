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
import logging
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.DeviceError import DeviceError, DeviceConfigError, DeviceNotFound
from lnst.Common.IpAddress import ipaddress
from lnst.Devices.Device import Device
from lnst.Devices.SoftDevice import SoftDevice

class VxlanDevice(SoftDevice):
    _name_template = "t_vxlan"
    _link_type = "vxlan"

    def __init__(self, ifmanager, *args, **kwargs):
        if "external" not in kwargs:
            self._mandatory_opts = ["vxlan_id"]
            if "group" in kwargs and "remote" in kwargs:
                raise DeviceError("group and remote cannot both be specified for vxlan")

            if "group" not in kwargs and "remote" not in kwargs:
                raise DeviceError("One of group or remote must be specified for vxlan")

            if "group" in kwargs and "realdev" not in kwargs:
                raise DeviceError("'group' requires realdev to be specified")

            if kwargs.get("remote", False) and ipaddress(kwargs["remote"]).is_multicast:
                logging.debug("ATTENTION: non-unicast remote IP set: %s" % str(kwargs["remote"]))

            if kwargs.get("group", False) and not ipaddress(kwargs["group"]).is_multicast:
                logging.debug("ATTENTION: non-multicast group IP set: %s" % str(kwargs["group"]))

        super(VxlanDevice, self).__init__(ifmanager, *args, **kwargs)

    @property
    def realdev(self):
        if self._nl_msg is None:
            return None
        try:
            if_id = int(self._get_linkinfo_data_attr("IFLA_VXLAN_LINK"))
            return self._if_manager.get_device(if_id)
        except (TypeError, DeviceNotFound):
            return None

    @realdev.setter
    def realdev(self, val):
        if not isinstance(val, Device):
            raise DeviceConfigError("realdev value must be a Device object.")

        self._set_linkinfo_data_attr("IFLA_VXLAN_LINK", val.ifindex)
        self._nl_link_sync("set")

    @property
    def vxlan_id(self):
        try:
            return int(self._get_linkinfo_data_attr("IFLA_VXLAN_ID"))
        except:
            return None

    @vxlan_id.setter
    def vxlan_id(self, val):
        if int(val) < 0 or int(val) > 16777215:
            raise DeviceConfigError("Invalid value, must be 0-16777215.")

        self._set_linkinfo_data_attr("IFLA_VXLAN_ID", int(val))
        self._nl_link_sync("set")

    @property
    def group(self):
        try:
            return ipaddress(self._get_linkinfo_data_attr("IFLA_VXLAN_GROUP"))
        except:
            return None

    @group.setter
    def group(self, val):
        self._set_linkinfo_data_attr("IFLA_VXLAN_GROUP", str(ipaddress(val)))
        self._nl_link_sync("set")

    @property
    def remote(self):
        try:
            return ipaddress(self._get_linkinfo_data_attr("IFLA_VXLAN_GROUP"))
        except:
            return None

    @remote.setter
    def remote(self, val):
        self._set_linkinfo_data_attr("IFLA_VXLAN_GROUP", str(ipaddress(val)))
        self._nl_link_sync("set")

    @property
    def dst_port(self):
        return int(self._get_linkinfo_data_attr("IFLA_VXLAN_PORT"))

    @dst_port.setter
    def dst_port(self, val):
        self._set_linkinfo_data_attr("IFLA_VXLAN_PORT", int(val))
        self._nl_link_sync("set")

    @property
    def external(self):
        return self._get_linkinfo_data_attr("IFLA_VXLAN_COLLECT_METADATA") is not None

    @external.setter
    def external(self, val):
        if val:
            self._set_linkinfo_data_attr("IFLA_VXLAN_COLLECT_METADATA", True)
        self._nl_link_sync("set")
