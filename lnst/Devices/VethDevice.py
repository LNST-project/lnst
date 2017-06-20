"""
Defines the VethDevice and PairedVethDevice classes.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from copy import deepcopy
from lnst.Common.ExecCmd import exec_cmd
from lnst.Devices.Device import Device
from lnst.Devices.SoftDevice import SoftDevice

class VethDevice(SoftDevice):
    _name_template = "veth"

    def __init__(self, ifmanager, *args, **kwargs):
        super(VethDevice, self).__init__(ifmanager, args, kwargs)

        self._name = kwargs.get("name", None)
        self._peer_name = kwargs.get("peer_name", None)

        if self._name is None:
            self._name = ifmanager.assign_name(self._name_template)

        if self._peer_name is None:
            self._peer_name = ifmanager.assign_name("peer_"+self._name_template)

    def _create(self):
        exec_cmd("ip link add {name} type veth peer name {peer}".
                 format(name=self.name,
                        peer=self._peer_name))

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

        self._if_manager.replace_dev(self.if_index, self)
