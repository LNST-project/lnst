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
from lnst.Common.DeviceError import DeviceError, DeviceConfigError
from lnst.Devices.Device import Device
from lnst.Devices.SoftDevice import SoftDevice

class VethDevice(SoftDevice):
    _name_template = "lveth"
    _link_type = "veth"

    def __init__(self, ifmanager, *args, **kwargs):
        if "peer_name" not in kwargs:
            if "name" in kwargs:
                kwargs["peer_name"] = ifmanager.assign_name("peer_"+kwargs["name"])
            else:
                kwargs["peer_name"] = ifmanager.assign_name("peer_"+self._name_template)

        super(VethDevice, self).__init__(ifmanager, *args, **kwargs)

    @property
    def peer_if_id(self):
        if self._nl_msg is None:
            return None

        return self._nl_msg.get_attr("IFLA_LINK")

    @property
    def peer_name(self):
        raise DeviceError(
            "The VethDevice peer_name property should not be accessed directly. "
            "Use the RemoteDevice.peer_name instead."
        )

    @peer_name.setter
    def peer_name(self, val):
        self._update_attr(str(val), "IFLA_LINKINFO", "IFLA_INFO_DATA",
                "VETH_INFO_PEER", "IFLA_IFNAME")
        self._nl_link_sync("set")

class PairedVethDevice(VethDevice):
    def __init__(self, ifmanager, *args, **kwargs):
        Device.__init__(self, ifmanager)

        self._peer_if_id = kwargs["peer_if_id"]

    def _create(self):
        peer = self._if_manager.get_device(self._peer_if_id)
        my_ifindex = peer.peer_if_id
        me = self._if_manager.get_device(my_ifindex)
        self._init_netlink(me._nl_msg)
        self._ip_addrs = deepcopy(me._ip_addrs)

        self._if_manager.replace_dev(self.ifindex, self)
