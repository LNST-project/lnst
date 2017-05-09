"""
Defines the VxlanDevice class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Common.ExecCmd import exec_cmd
from lnst.Devices.Device import DeviceError
from lnst.Devices.SoftDevice import SoftDevice

class VxlanDevice(SoftDevice):
    _name_template = "t_vxlan"

    def __init__(self, ifmanager, *args, **kwargs):
        super(VxlanDevice, self).__init__(ifmanager, args, kwargs)

        self._vxlan_id = int(kwargs["vxlan_id"])
        self._real_dev = kwargs.get("real_dev", None)
        self._group_ip = kwargs.get("group_ip", None)
        self._remote_ip = kwargs.get("remote_ip", None)
        self._dstport = int(kwargs.get("dst_port", 0))

        if self.group_ip is None and self.remote_ip is None:
            raise DeviceError("group or remote must be specified for vxlan")

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

    def create(self):
        dev_param = "dev %s" % self.real_dev.name if self.real_dev else ""

        if self.group_ip:
            group_or_remote = "group %s" % self.group_ip
        elif self.remote_ip:
            group_or_remote = "remote %s" % self.remote_ip

        exec_cmd("ip link add %s type vxlan id %d %s %s dstport %d"
                                % (self.name,
                                   self.vxlan_id,
                                   dev_param,
                                   group_or_remote,
                                   self.dstport))
