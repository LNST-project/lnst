"""
Defines the Ip6TnlDevice class.

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


class Ip6TnlDevice(SoftDevice):
    _name_template = "t_ip6tnl"
    _link_type = "ip6tnl"
    _mandatory_opts = ["local", "remote"]
    _mode_mapping = {"any": 0, "ipip6": 4, "ip6ip6": 41}
    _mode_mapping_reversed = dict((v, k) for k, v in _mode_mapping.items())

    def __init__(self, ifmanager, *args, **kwargs):
        if kwargs.get("mode", False) and not kwargs["mode"] in self._mode_mapping:
            raise DeviceError("Invalid mode specified for the ip6tnl device")

        super(Ip6TnlDevice, self).__init__(ifmanager, *args, **kwargs)

    @property
    def local(self):
        try:
            return ipaddress(self._get_linkinfo_data_attr("IFLA_IP6TNL_LOCAL"))
        except:
            return None

    @local.setter
    def local(self, val):
        self._set_linkinfo_data_attr("IFLA_IP6TNL_LOCAL", str(ipaddress(val)))
        self._nl_link_sync("set")

    @property
    def remote(self):
        try:
            return ipaddress(self._get_linkinfo_data_attr("IFLA_IP6TNL_REMOTE"))
        except:
            return None

    @remote.setter
    def remote(self, val):
        self._set_linkinfo_data_attr("IFLA_IP6TNL_REMOTE", str(ipaddress(val)))
        self._nl_link_sync("set")

    @property
    def mode(self):
        proto = self._get_linkinfo_data_attr("IFLA_IP6TNL_PROTO")
        return self._mode_mapping_reversed[proto]

    @mode.setter
    def mode(self, val):
        self._set_linkinfo_data_attr("IFLA_IP6TNL_PROTO", self._mode_mapping[val])
        self._nl_link_sync("set")

    @property
    def ttl(self):
        return self._get_linkinfo_data_attr("IFLA_IP6TNL_TTL")

    @ttl.setter
    def ttl(self, val):
        self._set_linkinfo_data_attr("IFLA_IP6TNL_TTL", val)
        self._nl_link_sync("set")
