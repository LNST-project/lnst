"""
Defines the GeneveDevice class.

Copyright 2021 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jtluka@redhat.com (Jan Tluka)
"""

import pyroute2
import logging
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.DeviceError import DeviceError, DeviceConfigError, DeviceNotFound
from lnst.Common.IpAddress import ipaddress, Ip4Address
from lnst.Devices.Device import Device
from lnst.Devices.SoftDevice import SoftDevice

class GeneveDevice(SoftDevice):
    _name_template = "t_gnv"
    _link_type = "geneve"
    _mandatory_opts = ["id", "remote"]

    @property
    def id(self):
        try:
            return int(self._get_linkinfo_data_attr("IFLA_GENEVE_ID"))
        except:
            return None

    @id.setter
    def id(self, val):
        if int(val) < 0 or int(val) > 16777215:
            raise DeviceConfigError("Invalid value, must be 0-16777215.")

        self._set_linkinfo_data_attr("IFLA_GENEVE_ID", int(val))
        self._nl_link_sync("set")

    @property
    def remote(self):
        # TODO: pyroute defines also IFLA_GENEVE_REMOTE6, this should be handled
        try:
            return ipaddress(self._get_linkinfo_data_attr("IFLA_GENEVE_REMOTE"))
        except:
            return None

    @remote.setter
    def remote(self, val):
        addr = ipaddress(val)
        if isinstance(addr, Ip4Address):
            self._set_linkinfo_data_attr("IFLA_GENEVE_REMOTE", str(addr))
        else:
            self._set_linkinfo_data_attr("IFLA_GENEVE_REMOTE6", str(addr))
        self._nl_link_sync("set")

    @property
    def dst_port(self):
        return int(self._get_linkinfo_data_attr("IFLA_GENEVE_PORT"))

    @dst_port.setter
    def dst_port(self, val):
        self._set_linkinfo_data_attr("IFLA_GENEVE_PORT", int(val))
        self._nl_link_sync("set")
