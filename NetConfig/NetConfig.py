"""
This module defines NetConfig class useful for netdevs config

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import logging
import copy
from NetConfigParse import NetConfigParse
from NetConfigDevNames import NetConfigDevNames
from NetConfigDevice import NetConfigDevice
from NetConfigDevice import NetConfigDeviceType
from NetConfigCommon import get_slaves

class NetConfig:
    def __init__(self, machine_xml_string, config_xml_string=None):
        parse = NetConfigParse(machine_xml_string)
        devnames = NetConfigDevNames()

        if config_xml_string:
            config = parse.parse_config(config_xml_string)
        else:
            '''
            No config is passed so make essential netdevices as they
            are listed in machine config and stores them into config
            '''
            mnetdevs = parse.get_machine_netdevs()
            config = copy.deepcopy(mnetdevs)
            for key in config:
                config[key]["phys_id"] = key

        devnames.assign_names(config)
        self._devnames = devnames
        self._config = config

    def _get_leafs(self):
        leafs = []
        for dev_id in self._config:
            netdev = self._config[dev_id]
            if len(get_slaves(netdev)) == 0:
                leafs.append(dev_id)
        return leafs

    def _get_masters(self, slave_dev_id):
        masters = []
        for dev_id in self._config:
            netdev = self._config[dev_id]
            if slave_dev_id in get_slaves(netdev):
                masters.append(dev_id)
        return masters

    def _get_dev_order(self):
        order = self._get_leafs()
        prev_order = []
        while order != prev_order:
            prev_order = list(order)
            for dev_id in prev_order:
                for master in self._get_masters(dev_id):
                    if master and not master in order:
                        order.append(master)
        return order

    def _get_used_types(self):
        types = set()
        for dev_id in self._config:
            netdev = self._config[dev_id]
            types.add(netdev["type"])
        return types

    def _types_init(self):
        for dev_type in self._get_used_types():
            NetConfigDeviceType(dev_type).type_init()

    def _types_cleanup(self):
        for dev_type in self._get_used_types():
            NetConfigDeviceType(dev_type).type_cleanup()

    def configure(self, dev_id):
        netdev = self._config[dev_id]
        device = NetConfigDevice(netdev, self._config)
        device.configure()
        device.up()

    def configure_all(self):
        self._types_init()
        dev_order = self._get_dev_order()
        for dev_id in dev_order:
            self.configure(dev_id)

    def deconfigure(self, dev_id):
        netdev = self._config[dev_id]
        device = NetConfigDevice(netdev, self._config)
        device.down()
        device.deconfigure()

    def deconfigure_all(self):
        dev_order = self._get_dev_order()
        for dev_id in reversed(dev_order):
            self.deconfigure(dev_id)
        self._types_cleanup()

    def dump_config(self):
        return copy.deepcopy(self._config)

    def _find_free_id(self):
        i = 1
        while i in self._config:
            i += 1
        return i

    def set_notes(self, dev_id, notes):
        self._config[dev_id]["notes"] = notes

    def get_notes(self, dev_id):
        return self._config[dev_id]["notes"]

    def netdev_add(self, dev_type, params=None):
        dev_id = self._find_free_id()
        netdev =  {"type": dev_type}
        if params:
            if "options" in params:
                netdev["options"] = params["options"]
            if "slaves" in params:
                netdev["slaves"] = params["slaves"]
        self._config[dev_id] = netdev
        self._devnames.assign_names(self._config)
        return dev_id

    def netdev_del(self, dev_id):
        del self._config[dev_id]

    def slave_add(self, dev_id, slave_dev_id):
        netdev = self._config[dev_id]
        if not "slaves" in netdev:
            netdev["slaves"] = []
        elif slave_dev_id in netdev["slaves"]:
            return False
        netdev["slaves"].append(slave_dev_id)
        device = NetConfigDevice(netdev, self._config)
        device.slave_add(slave_dev_id)
        return True

    def slave_del(self, dev_id, slave_dev_id):
        netdev = self._config[dev_id]
        if not "slaves" in netdev or not slave_dev_id in netdev["slaves"]:
            return False
        netdev["slaves"].remove(slave_dev_id)
        device = NetConfigDevice(netdev, self._config)
        device.slave_del(slave_dev_id)
        return True
