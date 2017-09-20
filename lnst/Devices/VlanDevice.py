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
from lnst.Devices.SoftDevice import SoftDevice

class VlanDevice(SoftDevice):
    _name_template = "t_vlan"
    _link_type = "vlan"

    def __init__(self, ifmanager, *args, **kwargs):
        super(VlanDevice, self).__init__(ifmanager, args, kwargs)

        self._real_dev = kwargs["real_dev"]
        self._vlan_id = int(kwargs["vlan_id"])

    @property
    def real_dev(self):
        return self._real_dev

    @property
    def vlan_id(self):
        return self._vlan_id

    def _create(self):
        with pyroute2.IPRoute() as ipr:
            try:
                data = {"attrs": [["IFLA_VLAN_ID", self._vlan_id]]}
                linkinfo = {"attrs": [["IFLA_INFO_KIND", self._link_type],
                                      ["IFLA_INFO_DATA", data]]}
                ipr.link("add", ifname=self.name, link=self._real_dev.ifindex,
                         IFLA_LINKINFO=linkinfo)
                self._if_manager.handle_netlink_msgs()
            except pyroute2.netlink.NetlinkError:
                log_exc_traceback()
                raise DeviceConfigError("Creating link %s failed." % self.name)
