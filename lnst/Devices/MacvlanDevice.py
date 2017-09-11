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
from lnst.Devices.SoftDevice import SoftDevice

class MacvlanDevice(SoftDevice):
    _name_template = "t_macvlan"
    _link_type = "macvlan"

    def __init__(self, ifmanager, *args, **kwargs):
        super(MacvlanDevice, self).__init__(ifmanager, args, kwargs)

        self._real_dev = kwargs["realdev"]
        self._mode = kwargs.get("mode", None)
        self._hwaddr = kwargs.get("hwaddr", None)

    def _create(self):
        with pyroute2.IPRoute() as ipr:
            try:
                ipr.link("add", IFLA_IFNAME=self.name,
                         IFLA_INFO_KIND=self._link_type,
                         IFLA_INFO_LINK=self._real_dev.ifindex,
                         IFLA_MACVLAN_MODE=self._mode,
                         IFLA_MACVLAN_MACADDR=self._hwaddr)
                self._if_manager.handle_netlink_msgs()
            except pyroute2.netlink.NetlinkError:
                log_exc_traceback()
                raise DeviceConfigError("Creating link %s failed." % self.name)
