"""
Defines the SitDevice class.

Copyright 2021 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jtluka@redhat.com (Jan Tluka)
"""

from lnst.Common.IpAddress import ipaddress
from lnst.Devices.SoftDevice import SoftDevice
from lnst.Common.DeviceError import DeviceError

class SitDevice(SoftDevice):
    _name_template = "t_sit"
    _link_type = "sit"
    _mandatory_opts = ["local", "remote"]
    _mode_mapping = {
        'any': 0,
        'ipv6/ipv4': 41,
        'ip6ip': 41,
        'ipip': 4,
        'ip4ip4': 4,
        'mpls/ipv4': 137,
        'mplsip': 137
    }

    def __init__(self, ifmanager, *args, **kwargs):
        if kwargs.get("mode", False) and not kwargs['mode'] in self._mode_mapping:
            raise DeviceError("Invalid mode specified for the sit device")

        super(SitDevice, self).__init__(ifmanager, *args, **kwargs)

    @property
    def local(self):
        try:
            return ipaddress(self._get_linkinfo_data_attr("IFLA_SIT_LOCAL"))
        except:
            return None

    @local.setter
    def local(self, val):
        self._set_linkinfo_data_attr("IFLA_SIT_LOCAL", str(ipaddress(val)))
        self._nl_link_sync("set")

    @property
    def remote(self):
        try:
            return ipaddress(self._get_linkinfo_data_attr("IFLA_SIT_REMOTE"))
        except:
            return None

    @remote.setter
    def remote(self, val):
        self._set_linkinfo_data_attr("IFLA_SIT_REMOTE", str(ipaddress(val)))
        self._nl_link_sync("set")

    @property
    def mode(self):
        return self._get_linkinfo_data_attr("IFLA_SIT_PROTO")

    @mode.setter
    def mode(self, val):
        self._set_linkinfo_data_attr("IFLA_SIT_PROTO", self._mode_mapping[val])
        self._nl_link_sync("set")
