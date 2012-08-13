"""
This module defines NetConfigDevNames class useful to obtain names for devices

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import logging
import os
from NetConfigCommon import get_option
from Common.NetUtils import normalize_hwaddr

class NetConfigDevNames:
    def __init__(self):
        self._scan = self._scan_netdevs()

    def _scan_netdevs(self):
        sys_dir = "/sys/class/net"
        scan = []
        for root, dirs, files in os.walk(sys_dir):
            if "lo" in dirs:
                dirs.remove("lo")
            for d in dirs:
                dev_path = os.path.join(sys_dir, d)
                addr_path = os.path.join(dev_path, "address")
                if not os.path.isfile(addr_path):
                    continue
                handle = open(addr_path, "rb")
                addr = handle.read()
                handle.close()
                addr = normalize_hwaddr(addr)
                scan.append({"name": d, "hwaddr": addr})
        return scan

    def rescan_netdevs(self):
        self._scan = self._scan_netdevs()

    def assign_name_by_scan(self, dev_id, netdev):
        if (not "hwaddr" in netdev or
            "name" in netdev): # name was previously assigned
            return

        hwaddr = normalize_hwaddr(netdev["hwaddr"])
        for entry in self._scan:
            if hwaddr == entry["hwaddr"]:
                netdev["name"] = entry["name"]
        if not "name" in netdev:
            logging.error("Name for addr \"%s\" (netdevice id \"%d\") not found"
                                                            % (hwaddr, dev_id))
            raise Exception

    def _is_name_used(self, name, config):
        for key in config:
            netdev = config[key]
            if "name" in netdev:
                if netdev["name"] == name:
                    return True
        return False

    def _assign_name_generic(self, prefix, netdev, config):
        index = 0
        while (self._is_name_used(prefix + str(index), config)):
            index += 1
        netdev["name"] = prefix + str(index)

    def _assign_name_bond(self, netdev, config):
        self._assign_name_generic("t_bond", netdev, config)

    def _assign_name_bridge(self, netdev, config):
        self._assign_name_generic("t_br", netdev, config)

    def _assign_name_macvlan(self, netdev, config):
        self._assign_name_generic("t_macvlan", netdev, config)

    def _assign_name_team(self, netdev, config):
        self._assign_name_generic("t_team", netdev, config)

    def _assign_name_vlan(self, netdev, config):
        real_netdev = config[netdev["slaves"][0]]
        vlan_tci = get_option(netdev, "vlan_tci")
        netdev["name"] = "%s.%s" % (real_netdev["name"], vlan_tci)

    def assign_name(self, dev_id, config):
        netdev = config[dev_id]
        if "name" in netdev:
            return
        dev_type = netdev["type"]
        if dev_type == "eth":
            self.assign_name_by_scan(dev_id, netdev)
        elif dev_type == "bond":
            self._assign_name_bond(netdev, config)
        elif dev_type == "bridge":
            self._assign_name_bridge(netdev, config)
        elif dev_type == "macvlan":
            self._assign_name_macvlan(netdev, config)
        elif dev_type == "team":
            self._assign_name_team(netdev, config)
        elif dev_type == "vlan":
            self._assign_name_vlan(netdev, config)
