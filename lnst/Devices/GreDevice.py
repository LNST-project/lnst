"""
Defines the GreDevice class.

Copyright 2021 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jtluka@redhat.com (Jan Tluka)
"""

from lnst.Common.IpAddress import ipaddress
from lnst.Devices.SoftDevice import SoftDevice


class GreDevice(SoftDevice):
    _name_template = "t_gre"
    _link_type = "gre"
    _mandatory_opts = ["remote"]

    @property
    def local(self):
        try:
            return ipaddress(self._get_linkinfo_data_attr("IFLA_GRE_LOCAL"))
        except:
            return None

    @local.setter
    def local(self, val):
        self._set_linkinfo_data_attr("IFLA_GRE_LOCAL", str(ipaddress(val)))
        self._nl_link_sync("set")

    @property
    def remote(self):
        try:
            return ipaddress(self._get_linkinfo_data_attr("IFLA_GRE_REMOTE"))
        except:
            return None

    @remote.setter
    def remote(self, val):
        self._set_linkinfo_data_attr("IFLA_GRE_REMOTE", str(ipaddress(val)))
        self._nl_link_sync("set")
