"""
This module defines common stuff for switch drivers

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

class SwitchOperations:
    '''
    This class defines abstract methods which should be implemented
    by individual drivers
    '''
    def list_ports(self):
        raise NotImplementedError()

    def list_vlans(self):
        raise NotImplementedError()

    def vlan_add(self, name, vlan_id):
        raise NotImplementedError()

    def vlan_del(self, vlan_id):
        raise NotImplementedError()

    def port_vlan_add(self, port_id, vlan_id, tagged):
        raise NotImplementedError()

    def port_vlan_del(self, port_id, vlan_id, tagged):
        raise NotImplementedError()

    def cleanup(self):
        raise NotImplementedError()

class SwitchDriverGeneric(SwitchOperations):
    def __init__(self, config):
        self._config = config

    def configure(self):
        for vlan_id in self._config["vlans"]:
            vlan = self._config["vlans"][vlan_id]
            vlan_name = vlan["name"]
            self.vlan_add(vlan_name, vlan_id)
            for port_id in vlan["ports"]:
                port = vlan["ports"][port_id]
                tagged = port["tagged"]
                self.port_vlan_add(port_id, vlan_id, tagged)
