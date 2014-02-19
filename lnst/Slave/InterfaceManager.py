"""
This module defines the InterfaceManager class that contains a database of
the available devices, handles netlink messages updating these devices and
provides an interface for creating software interfaces from config objects.

Copyright 2014 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import logging
from lnst.Slave.NetConfigDevice import NetConfigDevice
from lnst.Slave.NetConfigCommon import get_option
from lnst.Common.NetUtils import normalize_hwaddr
from lnst.Common.NetUtils import scan_netdevs
from lnst.Common.ExecCmd import exec_cmd
from pyroute2 import IPRSocket
from pyroute2.netlink.iproute import RTM_NEWLINK
from pyroute2.netlink.iproute import RTM_DELLINK

class IfMgrError(Exception):
    pass

class InterfaceManager(object):
    def __init__(self):
        self._devices = {}
        self._id_mapping = {} #id from the ctl to device

        self._nl_socket = IPRSocket()
        self._nl_socket.bind()

        self.rescan_devices()

    def map_if(self, if_id, if_index):
        if if_id in self._id_mapping:
            raise IfMgrError("Interface already mapped.")
        elif if_index not in self._devices:
            raise IfMgrError("No interface with index %s found." % if_index)

        self._id_mapping[if_id] = self._devices[if_index]
        return

    def clear_if_mapping(self):
        self._id_mapping = {}

    def get_nl_socket(self):
        return self._nl_socket

    def rescan_devices(self):
        self._devices = {}
        devs = scan_netdevs()
        for dev in devs:
            if dev['index'] not in self._devices:
                device = Device(self)
                device.init_netlink(dev['netlink_msg'])

                self._devices[dev['index']] = device

    def handle_netlink_msgs(self, msgs):
        for msg in msgs:
            self._handle_netlink_msg(msg)

    def _handle_netlink_msg(self, msg):
        if msg['header']['type'] == RTM_NEWLINK:
            if msg['index'] in self._devices:
                self._devices[msg['index']].update_netlink(msg)
            else:
                dev = None
                for d in self._id_mapping.values():
                    d_cfg = d.get_conf_dict()
                    if d.get_if_index() == None and\
                       d_cfg["name"] == msg.get_attr("IFLA_IFNAME"):
                            dev = d
                            break
                if dev == None:
                    dev = Device(self)
                dev.init_netlink(msg)
                self._devices[msg['index']] = dev
        elif msg['header']['type'] == RTM_DELLINK:
            if msg['index'] in self._devices:
                del self._devices[msg['index']]
        else:
            return

    def get_mapped_device(self, if_id):
        if if_id in self._id_mapping:
            return self._id_mapping[if_id]
        else:
            raise IfMgrError("No device with id %s mapped." % if_id)

    def get_mapped_devices(self):
        return self._id_mapping

    def get_device(self, if_index):
        if if_index in self._devices:
            return self._devices[if_index]
        else:
            return None

    def get_devices(self):
        return self._devices.values()

    def get_device_by_hwaddr(self, hwaddr):
        for dev in self._devices.values():
            if dev.get_hwaddr() == hwaddr:
                return dev
        return None

    def deconfigure_all(self):
        for dev in self._devices.itervalues():
            dev.clear_configuration()

    def create_device_from_config(self, if_id, config):
        if config["type"] == "eth":
            raise IfMgrError("Ethernet devices can't be created.")

        config["name"] = self.assign_name(config)

        device = Device(self)
        device.set_configuration(config)
        device.configure()

        self._id_mapping[if_id] = device
        return config["name"]

    def _is_name_used(self, name):
        for device in self._devices.itervalues():
            if name == device.get_name():
                return True
        return False

    def _assign_name_generic(self, prefix):
        index = 0
        while (self._is_name_used(prefix + str(index))):
            index += 1
        return prefix + str(index)

    def assign_name(self, config):
        if "name" in config:
            return config["name"]
        dev_type = config["type"]
        if dev_type == "eth":
            if (not "hwaddr" in config or
                "name" in config):
                return
            hwaddr = normalize_hwaddr(netdev["hwaddr"])
            for dev in self._devices:
                if dev.get_hwaddr() == hwaddr:
                    return dev.get_name()
        elif dev_type == "bond":
            return self._assign_name_generic("t_bond")
        elif dev_type == "bridge":
            return self._assign_name_generic("t_br")
        elif dev_type == "macvlan":
            return self._assign_name_generic("t_macvlan")
        elif dev_type == "team":
            return self._assign_name_generic("t_team")
        elif dev_type == "vlan":
            netdev_name = self.get_mapped_device(config["slaves"][0]).get_name()
            vlan_tci = get_option(config, "vlan_tci")
            prefix = "%s.%s_" % (netdev_name, vlan_tci)
            return self._assign_name_generic(prefix)

class Device(object):
    def __init__(self, if_manager):
        self._configured = False

        self._if_index = None
        self._hwaddr = None
        self._name = None
        self._conf = None
        self._conf_dict = None
        self._ip = None
        self._state = None
        self._master = None

        self._if_manager = if_manager

    def init_netlink(self, nl_msg):
        self._if_index = nl_msg['index']
        self._hwaddr = normalize_hwaddr(nl_msg.get_attr("IFLA_ADDRESS"))
        self._name = nl_msg.get_attr("IFLA_IFNAME")
        self._state = nl_msg.get_attr("IFLA_OPERSTATE")
        self._ip = None #TODO
        self._master = nl_msg.get_attr("IFLA_MASTER")

    def update_netlink(self, nl_msg):
        if self._if_index == nl_msg['index']:
            self._hwaddr = normalize_hwaddr(nl_msg.get_attr("IFLA_ADDRESS"))
            self._name = nl_msg.get_attr("IFLA_IFNAME")
            self._ip = None #TODO
            self._master = nl_msg.get_attr("IFLA_MASTER")
            #send update msg

    def get_if_index(self):
        return self._if_index

    def get_hwaddr(self):
        return self._hwaddr

    def get_name(self):
        return self._name

    def get_ip_conf(self):
        return self._ip

    def is_configured(self):
        return self._configured

    def get_conf_dict(self):
        return self._conf_dict

    def set_configuration(self, conf):
        self.clear_configuration()
        if "name" not in conf or conf["name"] == None:
            conf["name"] = self._name
        self._conf_dict = conf
        self._conf = NetConfigDevice(conf, self._if_manager)

    def get_configuration(self):
        return self._conf

    def clear_configuration(self):
        if self._master != None:
            master_dev = self._if_manager.get_device(self._master)
            if master_dev != None:
                master_dev.clear_configuration()

        if self._conf != None:
            self.down()
            self.deconfigure()
            self._conf = None
            self._conf_dict = None

    def configure(self):
        if self._conf != None and not self._configured:
            self._conf.configure()
            self._configured = True

    def deconfigure(self):
        if self._master != None:
            master_dev = self._if_manager.get_device(self._master)
            if master_dev != None:
                master_dev.deconfigure()

        if self._conf != None and self._configured:
            self._conf.deconfigure()
            self._configured = False

    def up(self):
        if self._conf != None:
            self._conf.up()
        else:
            exec_cmd("ip link set %s up" % self._name)

    def down(self):
        if self._conf != None:
            self._conf.down()
        else:
            exec_cmd("ip link set %s down" % self._name)
