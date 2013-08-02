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
from lnst.Slave.NetConfigDevNames import NetConfigDevNames
from lnst.Slave.NetConfigDevice import NetConfigDevice
from lnst.Slave.NetConfigDevice import NetConfigDeviceType
from lnst.Slave.NetConfigCommon import get_slaves

class NetConfig:
    def __init__(self):
        devnames = NetConfigDevNames()
        config = {}
        self._devnames = devnames
        self._config = config
        self._dev_configs = {}

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

    def add_interface_config(self, if_id, config):
        dev_type = config["type"]
        class_initialized = dev_type in self._get_used_types()

        self._config[if_id] = config

        self._devnames.rescan_netdevs()
        self._devnames.assign_name(if_id, self._config)

        dev_config = NetConfigDevice(config, self._config)
        self._dev_configs[if_id] = dev_config

        if not class_initialized:
            logging.info("Initializing '%s' device class", dev_type)
            dev_config.type_init()

    def remove_interface_config(self, if_id):
        config = self._config[if_id]
        del self._config[if_id]
        del self._dev_configs[if_id]

        dev_type = config["type"]
        if not dev_type in self._get_used_types():
            logging.info("Cleaning up '%s' device class.", dev_type)
            NetConfigDeviceType(config, self._config).type_cleanup()

    def get_interface_config(self, if_id):
        return self._config[if_id]

    def configure(self, dev_id):
        device = self._dev_configs[dev_id]
        device.configure()
        device.up()

    def configure_all(self):
        dev_order = self._get_dev_order()
        for dev_id in dev_order:
            self.configure(dev_id)

    def deconfigure(self, dev_id):
        device = self._dev_configs[dev_id]
        device.down()
        device.deconfigure()

    def deconfigure_all(self):
        dev_order = self._get_dev_order()
        for dev_id in reversed(dev_order):
            self.deconfigure(dev_id)

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

        self._devnames.rescan_netdevs()
        self._devnames.assign_name(dev_id, self._config)
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

    def cleanup(self):
        for dev_id in self._config.keys():
            del self._config[dev_id]
        for dev_id in self._dev_configs.keys():
            del self._dev_configs[dev_id]
        self._devnames.rescan_netdevs()
