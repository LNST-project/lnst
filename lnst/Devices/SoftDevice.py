"""
Defines the SoftDevice class.

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
from lnst.Devices.Device import Device

class SoftDevice(Device):
    _name_template = "soft_dev"
    _link_type = ""

    def __init__(self, ifmanager, *args, **kwargs):
        super(SoftDevice, self).__init__(ifmanager)

        self._name = kwargs.get("name", None)
        if self._name is None:
            self._name = ifmanager.assign_name(self._name_template)

    @property
    def name(self):
        try:
            return super(SoftDevice, self).name
        except:
            return self._name

    def _create(self):
        with pyroute2.IPRoute() as ipr:
            try:
                ipr.link("add", ifname=self.name, kind=self._link_type)
                self._if_manager.handle_netlink_msgs()
            except pyroute2.netlink.NetlinkError:
                log_exc_traceback()
                raise DeviceConfigError("Creating link %s failed." % self.name)

    def destroy(self):
        with pyroute2.IPRoute() as ipr:
            try:
                ipr.link("del", index=self.ifindex)
                self._if_manager.handle_netlink_msgs()
            except pyroute2.netlink.NetlinkError:
                log_exc_traceback()
                raise DeviceConfigError("Deleting link %s failed." % self.name)
        return True
