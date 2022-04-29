"""
Defines the VtiDevice and Vti6Device classes.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Common.IpAddress import ipaddress
from lnst.Common.DeviceError import DeviceConfigError
from lnst.Devices.Device import Device
from lnst.Devices.SoftDevice import SoftDevice

class _BaseVtiDevice(SoftDevice):
    _link_type = "vti"

    def __init__(self, ifmanager, *args, **kwargs):
        if "local" not in kwargs and "remote" not in kwargs:
            raise DeviceConfigError("One of local/remote MUST be defined.")

        if "key" in kwargs:
            try:
                int(kwargs["key"])
            except ValueError:
                raise DeviceConfigError("key value must be an integer.")
            kwargs["ikey"] = kwargs["key"]
            kwargs["okey"] = kwargs["key"]
            del kwargs["key"]

        super(_BaseVtiDevice, self).__init__(ifmanager, *args, **kwargs)

    @property
    def ikey(self):
        try:
            return int(self._get_linkinfo_data_attr("IFLA_VTI_IKEY"))
        except:
            return None

    @ikey.setter
    def ikey(self, val):
        self._set_linkinfo_data_attr("IFLA_VTI_IKEY", int(val))
        self._nl_link_sync("set")

    @property
    def okey(self):
        try:
            return int(self._get_linkinfo_data_attr("IFLA_VTI_OKEY"))
        except:
            return None

    @okey.setter
    def okey(self, val):
        self._set_linkinfo_data_attr("IFLA_VTI_OKEY", int(val))
        self._nl_link_sync("set")

    @property
    def local(self):
        try:
            return ipaddress(self._get_linkinfo_data_attr("IFLA_VTI_LOCAL"))
        except:
            return None

    @local.setter
    def local(self, val):
        self._set_linkinfo_data_attr("IFLA_VTI_LOCAL", str(ipaddress(val)))
        self._nl_link_sync("set")

    @property
    def remote(self):
        try:
            return ipaddress(self._get_linkinfo_data_attr("IFLA_VTI_REMOTE"))
        except:
            return None

    @remote.setter
    def remote(self, val):
        self._set_linkinfo_data_attr("IFLA_VTI_REMOTE", str(ipaddress(val)))
        self._nl_link_sync("set")

    @property
    def realdev(self):
        if self._nl_msg is None:
            return None

        if_id = self._get_linkinfo_data_attr("IFLA_VTI_LINK")
        return self._if_manager.get_device(if_id)

    @realdev.setter
    def realdev(self, val):
        if not isinstance(val, Device):
            raise DeviceConfigError("realdev value must be a Device object.")

        self._set_linkinfo_data_attr("IFLA_VTI_LINK", val.ifindex)
        self._nl_link_sync("set")

    @property
    def vti_type(self):
        raise NotImplementedError()

class VtiDevice(_BaseVtiDevice):
    vti_type = "vti"
    _link_type = "vti"
    _name_template = "t_vti"

class Vti6Device(_BaseVtiDevice):
    vti_type = "vti6"
    _link_type = "vti6"
    _name_template = "t_ip6vti"
