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
    def __init__(self, server_handler):
        self._devices = {} #if_index to device
        self._id_mapping = {} #id from the ctl to if_index
        self._tmp_mapping = {} #id from the ctl to newly created device

        self._nl_socket = IPRSocket()
        self._nl_socket.bind()

        self.rescan_devices()

        self._server_handler = server_handler

    def map_if(self, if_id, if_index):
        if if_id in self._id_mapping:
            raise IfMgrError("Interface already mapped.")
        elif if_index not in self._devices:
            raise IfMgrError("No interface with index %s found." % if_index)

        self._id_mapping[if_id] = if_index
        return

    def clear_if_mapping(self):
        self._id_mapping = {}

    def reconnect_netlink(self):
        if self._nl_socket != None:
            self._nl_socket.close()
            self._nl_socket = None
        self._nl_socket = IPRSocket()
        self._nl_socket.bind()

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
                update_msg = self._devices[msg['index']].update_netlink(msg)
                if update_msg != None:
                    for if_id, if_index in self._id_mapping.iteritems():
                        if if_index == msg['index']:
                            update_msg["if_id"] = if_id
                            break
                    if "if_id" in update_msg:
                        self._server_handler.send_data_to_ctl(update_msg)
            else:
                dev = None
                for if_id, d in self._tmp_mapping.items():
                    d_cfg = d.get_conf_dict()
                    if d_cfg["name"] == msg.get_attr("IFLA_IFNAME"):
                        dev = d
                        self._id_mapping[if_id] = msg['index']
                        del self._tmp_mapping[if_id]
                        break
                if dev == None:
                    dev = Device(self)
                dev.init_netlink(msg)
                self._devices[msg['index']] = dev
        elif msg['header']['type'] == RTM_DELLINK:
            if msg['index'] in self._devices:
                dev = self._devices[msg['index']]
                if dev.get_netns() == None and dev.get_conf_dict() == None:
                    dev.del_link()
                    del self._devices[msg['index']]
        else:
            return

    def get_mapped_device(self, if_id):
        if if_id in self._id_mapping:
            if_index = self._id_mapping[if_id]
            return self._devices[if_index]
        elif if_id in self._tmp_mapping:
            return self._tmp_mapping[if_id]
        else:
            raise IfMgrError("No device with id %s mapped." % if_id)

    def get_mapped_devices(self):
        ret = {}
        for if_id, if_index in self._id_mapping.iteritems():
            ret[if_id] = self._devices[if_index]
        for if_id, dev in self._tmp_mapping:
            ret[if_id] = self._tmp_mapping[if_id]
        return ret

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
        device.create()

        self._tmp_mapping[if_id] = device
        return config["name"]

    def create_device_pair(self, if_id1, config1, if_id2, config2):
        name1, name2 = self.assign_name(config1)
        config1["name"] = name1
        config2["name"] = name2
        config1["peer_name"] = name2
        config2["peer_name"] = name1

        device1 = Device(self)
        device2 = Device(self)

        device1.set_configuration(config1)
        device2.set_configuration(config2)
        device1.create()

        self._tmp_mapping[if_id1] = device1
        self._tmp_mapping[if_id2] = device2
        return name1, name2

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

    def _assign_name_pair(self, prefix):
        index1 = 0
        index2 = 0
        while (self._is_name_used(prefix + str(index1))):
            index1 += 1
        index2 = index1 + 1
        while (self._is_name_used(prefix + str(index2))):
            index2 += 1
        return prefix + str(index1), prefix + str(index2)

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
        elif dev_type == "bridge" or dev_type == "ovs_bridge":
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
        elif dev_type == "veth":
            return self._assign_name_pair("veth")
        elif dev_type == "vti":
            return self._assign_name_generic("vti")
        else:
            return self._assign_name_generic("dev")

class Device(object):
    def __init__(self, if_manager):
        self._initialized = False
        self._configured = False
        self._created = False

        self._if_index = None
        self._hwaddr = None
        self._name = None
        self._conf = None
        self._conf_dict = None
        self._ip = None
        self._ifi_type = None
        self._state = None
        self._master = {"primary": None, "other": []}
        self._slaves = []
        self._netns = None

        self._if_manager = if_manager

    def init_netlink(self, nl_msg):
        self._if_index = nl_msg['index']
        self._ifi_type = nl_msg['ifi_type']
        self._hwaddr = normalize_hwaddr(nl_msg.get_attr("IFLA_ADDRESS"))
        self._name = nl_msg.get_attr("IFLA_IFNAME")
        self._state = nl_msg.get_attr("IFLA_OPERSTATE")
        self._ip = None #TODO
        self.set_master(nl_msg.get_attr("IFLA_MASTER"), primary=True)
        self._netns = None

        self._initialized = True

    def update_netlink(self, nl_msg):
        if self._if_index == nl_msg['index']:
            self._hwaddr = normalize_hwaddr(nl_msg.get_attr("IFLA_ADDRESS"))
            self._name = nl_msg.get_attr("IFLA_IFNAME")
            self._state = nl_msg.get_attr("IFLA_OPERSTATE")
            self._ip = None #TODO
            self.set_master(nl_msg.get_attr("IFLA_MASTER"), primary=True)

            link = nl_msg.get_attr("IFLA_LINK")
            if link != None:
                # IFLA_LINK is an index of device that's closer to physical
                # interface in the stack, e.g. index of eth0 for eth0.100
                # so to properly deconfigure the stack we have to save
                # parent index in the child device; this is the opposite
                # to IFLA_MASTER
                link_dev = self._if_manager.get_device(link)
                if link_dev != None:
                    link_dev.set_master(self._if_index, primary=False)
                # This reference shouldn't change - you can't change the realdev
                # of a vlan, you need to create a new vlan. Therefore the
                # the following add_slave shouldn't be a problem.
                self.add_slave(link)

            if self._conf_dict:
                self._conf_dict["name"] = self._name

            self._initialized = True

            #return an update message that will be sent to the controller
            return {"type": "if_update",
                    "devname": self._name,
                    "hwaddr": self._hwaddr}
        return None

    def del_link(self):
        if self._master["primary"]:
            primary_id = self._master["primary"]
            primary_dev = self._if_manager.get_device(primary_id)
            if primary_dev:
                primary_dev.del_slave(self._if_index)

        for m_id in self._master["other"]:
            m_dev = self._if_manager.get_device(m_id)
            if m_dev:
                m_dev.del_slave(self._if_index)

        for dev_id in self._slaves:
            dev = self._if_manager.get_device(dev_id)
            if dev != None:
                dev.del_master(self._if_index)

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

        if not self._initialized:
            self._name = conf["name"]

    def get_configuration(self):
        return self._conf

    def del_configuration(self):
        self._conf = None
        self._conf_dict = None

    def clear_configuration(self):
        if self._master["primary"]:
            primary_id = self._master["primary"]
            primary_dev = self._if_manager.get_device(primary_id)
            if primary_dev:
                primary_dev.clear_configuration()

        for m_id in self._master["other"]:
            m_dev = self._if_manager.get_device(m_id)
            if m_dev:
                m_dev.clear_configuration()

        if self._conf != None:
            self.down()
            self.deconfigure()
            self.destroy()
            self._conf = None
            self._conf_dict = None

    def set_master(self, if_index, primary=True):
        if primary:
            prev_master_id = self._master["primary"]
            if prev_master_id != None and if_index != prev_master_id:
                prev_master_dev = self._if_manager.get_device(prev_master_id)
                if prev_master_dev != None:
                    prev_master_dev.del_slave(self._if_index)

            self._master["primary"] = if_index
            if self._master["primary"] != None:
                master_id = self._master["primary"]
                master_dev = self._if_manager.get_device(master_id)
                if master_dev != None:
                    master_dev.add_slave(self._if_index)
        elif if_index not in self._master["other"]:
            self._master["other"].append(if_index)

    def del_master(self, if_index):
        if self._master["primary"] == if_index:
            self._master["primary"] = None
        elif if_index in self._master["other"]:
            self._master["other"].remove(if_index)

    def add_slave(self, if_index):
        if if_index not in self._slaves:
            self._slaves.append(if_index)

    def del_slave(self, if_index):
        if if_index in self._slaves:
            self._slaves.remove(if_index)

    def create(self):
        if self._conf != None and not self._created:
            self._conf.create()
            self._created = True
            return True
        return False

    def destroy(self):
        if self._conf != None and self._created:
            self._conf.destroy()
            self._created = False
            return True
        return False

    def configure(self):
        if self._conf != None and not self._configured:
            self._conf.configure()
            self._configured = True

    def deconfigure(self):
        if self._master["primary"]:
            primary_id = self._master["primary"]
            primary_dev = self._if_manager.get_device(primary_id)
            if primary_dev:
                primary_dev.deconfigure()

        for m_id in self._master["other"]:
            m_dev = self._if_manager.get_device(m_id)
            if m_dev:
                m_dev.deconfigure()

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

    def set_netns(self, netns):
        self._netns = netns
        return

    def get_netns(self):
        return self._netns
