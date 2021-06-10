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

    def __init__(self, ifmanager, *args, **kwargs):
        if "external" not in kwargs:
            self._mandatory_opts = ["remote"]

        super(GreDevice, self).__init__(ifmanager, *args, **kwargs)

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

    @property
    def external(self):
        return self._get_linkinfo_data_attr("IFLA_GRE_COLLECT_METADATA") is not None

    @external.setter
    def external(self, val):
        if val:
            self._set_linkinfo_data_attr("IFLA_GRE_COLLECT_METADATA", True)
        self._nl_link_sync("set")
