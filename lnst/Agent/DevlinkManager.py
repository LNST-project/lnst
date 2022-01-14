"""
This module defines the DevlinkManager class that contains a database of
the available devlink devices, handles netlink messages updating these devices.

Copyright 2016 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jiri@mellanox.com (Jiri Pirko)
"""

try:
    from pyroute2 import DL
    from pyroute2.netlink.exceptions import NetlinkError

    def dl_open():
        try:
            return DL()
        except NetlinkError:
            return None

except ImportError:
    class DL(object):
        def port_list(self):
            return []

        def close(self):
            return

    def dl_open():
        return DL()

class DevlinkManager(object):
    def __init__(self):
        self.rescan_ports()

    def rescan_ports(self):
        self._ports = []

        dl = dl_open()
        if not dl:
            return

        try:
            for q in dl.port_list():
                dl_port = {}
                dl_port["bus_name"] = q.get_attr('DEVLINK_ATTR_BUS_NAME')
                dl_port["dev_name"] = q.get_attr('DEVLINK_ATTR_DEV_NAME')
                dl_port["port_index"] = q.get_attr('DEVLINK_ATTR_PORT_INDEX')
                dl_port["port_netdev_name"] = q.get_attr('DEVLINK_ATTR_PORT_NETDEV_NAME')
                self._ports.append(dl_port)
        except:
            raise
        finally:
            dl.close()

    def get_port(self, ifname):
        for dl_port in self._ports:
            if dl_port["port_netdev_name"] == ifname:
                return dl_port
        return None
