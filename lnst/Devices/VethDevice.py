"""
Defines the VethDevice and PairedVethDevice classes.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import pyroute2
from copy import deepcopy
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.DeviceError import DeviceConfigError
from lnst.Devices.Device import Device
from lnst.Devices.SoftDevice import SoftDevice

class VethDevice(SoftDevice):
    _name_template = "veth"
    _link_type = "veth"

    def __init__(self, ifmanager, *args, **kwargs):
        super(VethDevice, self).__init__(ifmanager, args, kwargs)

        self._name = kwargs.get("name", None)
        self._peer_name = kwargs.get("peer_name", None)

        if self._name is None:
            self._name = ifmanager.assign_name(self._name_template)

        if self._peer_name is None:
            self._peer_name = ifmanager.assign_name("peer_"+self._name_template)

    def _create(self):
        with pyroute2.IPRoute() as ipr:
            try:
                data = {"attrs": [["VETH_INFO_PEER", self._peer_name]]}
                linkinfo = {"attrs": [["IFLA_INFO_KIND", self._link_type],
                                      ["IFLA_INFO_DATA", data]]}
                ipr.link("add", ifname=self.name, link=self._real_dev.ifindex,
                         IFLA_LINKINFO=linkinfo)
                self._if_manager.handle_netlink_msgs()
            except pyroute2.netlink.NetlinkError:
                log_exc_traceback()
                raise DeviceConfigError("Creating link %s failed." % self.name)

    @property
    def peer(self):
        if self._nl_msg is None:
            return None

        peer_if_id = self._nl_msg.get_attr("IFLA_LINK")
        return self._if_manager.get_device(peer_if_id)

class PairedVethDevice(VethDevice):
    def __init__(self, ifmanager, *args, **kwargs):
        Device.__init__(self, ifmanager)

        self._peer_if_id = kwargs["peer_if_id"]

    def _create(self):
        peer = self._if_manager.get_device(self._peer_if_id)
        me = peer.peer
        self._init_netlink(me._nl_msg)
        self._ip_addrs = deepcopy(me._ip_addrs)

        self._if_manager.replace_dev(self.ifindex, self)
