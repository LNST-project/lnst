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

    _link_map = {"name": "IFLA_IFNAME"}
    _linkinfo_data_map = {"peer_name": "VETH_INFO_PEER"}

    def __init__(self, ifmanager, *args, **kwargs):
        if "name" not in kwargs:
            kwargs["name"] = ifmanager.assign_name(self._name_template)

        if "peer_name" not in kwargs:
            kwargs["peer_name"] = ifmanager.assign_name("peer_"+self._name_template)

        super(VethDevice, self).__init__(ifmanager, *args, **kwargs)

    def _parse_linkinfo_data(self, **kwargs):
        data = {"attrs": []}
        for key, nl_attr in self._linkinfo_data_map.items():
            if key in kwargs:
                val = kwargs.pop(key)
                if key == "peer_name":
                    val = {"attrs": [("IFLA_IFNAME", val)]}
                data["attrs"].append((nl_attr, val))
        return data

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
