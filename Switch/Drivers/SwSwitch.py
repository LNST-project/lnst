"""
This module defines software switch driver

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import logging
from Switch.SwitchDriversCommon import SwitchDriverGeneric
from Common.XmlRpc import ServerProxy

DefaultRPCPort = 9998

class SwSwitch(SwitchDriverGeneric):
    def init(self):
        info = self._config["info"]
        if "port" in info:
            port = info["port"]
        else:
            port = DefaultRPCPort
        hostname = info["hostname"]
        url = "http://%s:%d" % (hostname, port)
        self._rpc = ServerProxy(url)

    def list_ports(self):
        return self._rpc.list_ports()

    def list_vlans(self):
        return self._rpc.list_vlans()

    def vlan_add(self, name, vlan_id):
        return self._rpc.vlan_add(name, vlan_id)

    def vlan_del(self, vlan_id):
        return self._rpc.vlan_del(vlan_id)

    def port_vlan_add(self, port_id, vlan_id, tagged):
        return self._rpc.port_vlan_add(port_id, vlan_id, tagged)

    def port_vlan_del(self, port_id, vlan_id, tagged):
        return self._rpc.port_vlan_del(port_id, vlan_id, tagged)

    def cleanup(self):
        return self._rpc.cleanup()
