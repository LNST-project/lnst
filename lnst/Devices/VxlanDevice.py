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
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.DeviceError import DeviceError, DeviceConfigError
from lnst.Devices.SoftDevice import SoftDevice

class VxlanDevice(SoftDevice):
    _name_template = "t_vxlan"
    _link_type = "vxlan"

    def __init__(self, ifmanager, *args, **kwargs):
        super(VxlanDevice, self).__init__(ifmanager, args, kwargs)

        self._vxlan_id = int(kwargs["vxlan_id"])
        self._real_dev = kwargs.get("real_dev", None)
        self._group_ip = kwargs.get("group_ip", None)
        self._remote_ip = kwargs.get("remote_ip", None)
        self._dstport = int(kwargs.get("dst_port", 0))

        if self.group_ip is None and self.remote_ip is None:
            raise DeviceError("group or remote must be specified for vxlan")

        if self.group_ip is not None and self.remote_ip is not None:
            raise DeviceError("group and remote cannot both be specified for vxlan")

    @property
    def real_dev(self):
        return self._real_dev

    @property
    def vxlan_id(self):
        return self._vxlan_id

    @property
    def group_ip(self):
        return self._group_ip

    @property
    def remote_ip(self):
        return self._remote_ip

    @property
    def dst_port(self):
        return self._dst_port

    def _create(self):
        with pyroute2.IPRoute() as ipr:
            try:
                kwargs = {"IFLA_VXLAN_ID": self.vxlan_id,
                          "IFLA_VXLAN_PORT": self.dst_port}

                if self.real_dev:
                    kwargs["IFLA_VXLAN_LINK"] = self._real_dev.ifindex

                if self.group_ip:
                    kwargs["IFLA_VXLAN_GROUP"] = self.group_ip
                elif self.remote_ip:
                    kwargs["IFLA_VXLAN_GROUP"] = self.remote_ip

                ipr.link("add", IFLA_IFNAME=self.name,
                         IFLA_INFO_KIND=self._link_type, **kwargs)

                self._if_manager.handle_netlink_msgs()
            except pyroute2.netlink.NetlinkError:
                log_exc_traceback()
                raise DeviceConfigError("Creating link %s failed." % self.name)
