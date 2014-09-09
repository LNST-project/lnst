"""
This module defines multiple classes useful for configuring
multiple types of net devices, using NetworkManager

Copyright 2013 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olicthne@redhat.com (Ondrej Lichtner)
"""

import logging
import re
import sys
import dbus
import uuid
import socket, struct
import time
from lnst.Common.ExecCmd import exec_cmd
from lnst.Slave.NetConfigCommon import get_slaves, get_option, get_slave_option
from lnst.Common.Utils import kmod_in_use, bool_it
from lnst.Common.NetUtils import scan_netdevs
from lnst.Common.Utils import check_process_running
from lnst.Common.Config import lnst_config

NM_BUS = "org.freedesktop.NetworkManager"
OBJ_PRE = "/org/freedesktop/NetworkManager"
IF_PRE = NM_BUS

#NetworkManager constants for state values
_ACON_ACTIVATED = 2
_DEV_UNAVAILABLE = 20
_DEV_DISCONNECTED = 30

def is_nm_managed_by_name(dev_name):
    if not check_process_running("NetworkManager") or\
       not lnst_config.get_option("environment", "use_nm"):
        return False

    bus = dbus.SystemBus()
    nm_obj = bus.get_object(NM_BUS, OBJ_PRE)
    nm_if = dbus.Interface(nm_obj, IF_PRE)
    try:
        device_obj_path = nm_if.GetDeviceByIpIface(dev_name)
    except:
        #There is a higher possibility that if the interface doesn't exist
        #it's a software interface that can be created by NM so we say that it's
        #managed and check existance of physical interfaces sepparately
        return True

    dev = bus.get_object(NM_BUS, device_obj_path)
    dev_props = dbus.Interface(dev, "org.freedesktop.DBus.Properties")
    return dev_props.Get(IF_PRE + ".Device", "Managed")

def _dev_exists(hwaddr):
    devnames = scan_netdevs()
    for dev in devnames:
        if dev["hwaddr"] == hwaddr:
            return True

def get_nm_version():
    if not check_process_running("NetworkManager") or\
       not lnst_config.get_option("environment", "use_nm"):
        return ""

    bus = dbus.SystemBus()
    nm_obj = bus.get_object(NM_BUS, OBJ_PRE)
    nm_if = dbus.Interface(nm_obj, IF_PRE)

    props = dbus.Interface(nm_obj, "org.freedesktop.DBus.Properties")
    return props.Get(IF_PRE, "Version")

class NmConfigDeviceGeneric(object):
    '''
    Generic class for device manipulation all type classes should
    extend this one.
    '''
    _modulename = ""
    _moduleload = True
    _moduleparams = ""
    _cleanupcmd = ""

    _device_state = None
    _loop = None
    _wait_for = None


    def __init__(self, dev_config, if_manager):
        self._dev_config = dev_config
        self._if_manager = if_manager
        self._bus = dbus.SystemBus()
        self._nm_obj = self._bus.get_object(NM_BUS, OBJ_PRE)
        self._nm_if = dbus.Interface(self._nm_obj, IF_PRE)

        self._connection = None
        self._connection_added = False
        self._con_obj_path = None
        self._acon_obj_path = None

    def configure(self):
        pass

    def deconfigure(self):
        pass

    def create(self):
        pass

    def destroy(self):
        pass

    def slave_add(self, slave_id):
        pass

    def slave_del(self, slave_id):
        pass

    def up(self):
        if not self._connection_added:
            self._nm_add_connection()
        if self._connection_added:
            #NM would automatically activate the master connection, however
            #we want to have the record of which active connection that is
            if self._dev_config["master"] != None:
                master_id = self._dev_config["master"]
                master_dev = self._if_manager.get_mapped_device(master_id)
                master_dev.up()
            self._nm_activate_connection()

    def down(self):
        if self._connection_added:
            self._nm_deactivate_connection()

    @classmethod
    def type_init(self):
        pass

    @classmethod
    def type_cleanup(self):
        pass

    @classmethod
    def is_nm_managed(cls, dev_config, if_manager):
        if dev_config["netns"] != None:
            return False
        return is_nm_managed_by_name(dev_config["name"])

    def _wait_for_state(self, new_state, old_state, reason):
        self._device_state = new_state
        if self._device_state == self._wait_for:
            self._loop.quit()

    def _poll_loop(self, func, expected_val, *args):
        while True:
            if func(*args) == expected_val:
                break
            time.sleep(1)

    def _convert_hwaddr(self, dev_config):
        if "hwaddr" in dev_config:
            hwaddr = dev_config["hwaddr"]
        else:
            return None

        hw_nums = hwaddr.split(':')

        addr_bytes = []
        for i in hw_nums:
            addr_bytes.append(int(i, base=16))
        return dbus.Array(addr_bytes, 'y')

    def _nm_make_ip_settings(self, addrs):
        ipv4s = []
        ipv6s = []
        for addr in addrs:
            match = re.match("([^/]*)(/(\d*))?", addr)
            ip, mask = match.group(1,3)
            if not mask:
                mask = 0
            try:
                #IPv4 conversion into a 32bit number
                ip = struct.unpack("=I", socket.inet_pton(socket.AF_INET, ip))[0]
                ipv4s.append(dbus.Array([ip, mask, 0], signature='u'))
            except:
                #IPv6 conversion into a 16 byte array
                tmp = socket.inet_pton(socket.AF_INET6, ip)
                ip = []
                for i in tmp:
                    ip.append(ord(i))
                ip = dbus.Array(ip, signature='y')
                def_gateway = dbus.Array([0]*16, signature='y')
                ipv6s.append(tuple([ip,
                                    dbus.UInt32(mask),
                                    def_gateway]))

        if len(ipv4s)>0:
            s_ipv4 = dbus.Dictionary({
                'addresses': ipv4s,
                'method': 'manual'}, signature='sv')
        else:
            s_ipv4 = dbus.Dictionary({
                'method': 'disabled'}, signature='sv')
        if len(ipv6s)>0:
            s_ipv6 = dbus.Dictionary({
                'addresses': ipv6s,
                'method': 'manual'}, signature='sv')
        else:
            s_ipv6 = dbus.Dictionary({
                'method': 'ignore'}, signature='sv')

        return (s_ipv4, s_ipv6)

    def _nm_add_connection(self):
        #NM will succesfully add this connection but is unable to activate it...
        if self._connection["ipv4"]["method"] == "disabled" and\
           self._connection["ipv6"]["method"] == "ignore" and\
           "master" not in self._connection["connection"] and\
           self._connection["connection"]["type"] == "802-3-ethernet":
               return

        if not self._connection_added:
            bus = self._bus
            settings_obj = bus.get_object(NM_BUS, OBJ_PRE + "/Settings")
            settings_if = dbus.Interface(settings_obj, IF_PRE + ".Settings")
            self._con_obj_path = settings_if.AddConnection(self._connection)
            self._connection_added = True
            logging.debug("Added NM connection: %s" % self._con_obj_path)

    def _nm_rm_connection(self):
        if self._connection_added:
            bus = self._bus
            con_obj = bus.get_object(NM_BUS, self._con_obj_path)
            con_if = dbus.Interface(con_obj, IF_PRE + ".Settings.Connection")
            con_if.Delete()
            logging.debug("Removed NM connection: %s" % self._con_obj_path)
            self._connection_added = False
            self._con_obj_path = None

    def _nm_update_connection(self):
        if self._connection_added:
            bus = self._bus
            con_obj = bus.get_object(NM_BUS, self._con_obj_path)
            con_if = dbus.Interface(con_obj, IF_PRE + ".Settings.Connection")
            con_if.Update(self._connection)
            logging.debug("Updated NM connection: %s" % self._con_obj_path)

    def _nm_activate_connection(self):
        config = self._dev_config
        if self._acon_obj_path != None or\
           self._con_obj_path == None:
            return
        else:
            logging.info("Activating connection on interface %s"
                                                    % config["name"])
            bus = self._bus
            nm_if = self._nm_if

            try:
                device_obj_path = nm_if.GetDeviceByIpIface(config["name"])
            except:
                device_obj_path = "/"

            self._acon_obj_path = nm_if.ActivateConnection(
                                                self._con_obj_path,
                                                device_obj_path, "/")

            logging.debug("Device object path: %s" % device_obj_path)
            logging.debug("Connection object path: %s" % self._con_obj_path)
            logging.debug("Active connection object path: %s"
                                                % self._acon_obj_path)

            act_con = bus.get_object(NM_BUS, self._acon_obj_path)
            act_con_props = dbus.Interface(act_con,
                                           "org.freedesktop.DBus.Properties")
            self._poll_loop(act_con_props.Get,
                            _ACON_ACTIVATED,
                            IF_PRE + ".Connection.Active", "State")

    def _nm_deactivate_connection(self):
        config = self._dev_config
        if self._acon_obj_path == None:
            return
        else:
            logging.info("Deactivating connection on device %s"
                                                    % config["name"])
            logging.debug("Active connection object path: %s"
                                                    % self._acon_obj_path)
            self._nm_if.DeactivateConnection(self._acon_obj_path)
            self._acon_obj_path = None

    def nm_enslave(self, slave_type, master_uuid, slave_conf):
        self._connection["connection"]["slave_type"] = slave_type
        self._connection["connection"]["master"] = master_uuid
        self._connection.update(slave_conf)

        self._nm_update_connection()

    def nm_free(self):
        if "slave_type" in self._connection["connection"]:
            del self._connection["connection"]["slave_type"]
        if "master" in self._connection["connection"]:
            del self._connection["connection"]["master"]

        self._nm_update_connection()

class NmConfigDeviceEth(NmConfigDeviceGeneric):
    @classmethod
    def is_nm_managed(cls, dev_config, if_manager):
        managed = super(NmConfigDeviceEth, cls).is_nm_managed(dev_config,
                                                              if_manager)
        if _dev_exists(dev_config["hwaddr"]):
            return managed
        else:
            return False

    def up(self):
        config = self._dev_config

        bus = self._bus
        nm_if = self._nm_if

        device_obj_path = nm_if.GetDeviceByIpIface(config["name"])

        dev = bus.get_object(NM_BUS, device_obj_path)
        dev_props = dbus.Interface(dev, "org.freedesktop.DBus.Properties")

        state = dev_props.Get(IF_PRE + ".Device", "State")
        if state == _DEV_UNAVAILABLE:
            logging.info("Resetting interface so NM manages it.")
            exec_cmd("ip link set %s down" % config["name"])
            exec_cmd("ip link set %s up" % config["name"])

            self._poll_loop(dev_props.Get,
                            _DEV_DISCONNECTED,
                            IF_PRE + ".Device", "State")
        else:
            exec_cmd("ip link set %s up" % config["name"])

        super(NmConfigDeviceEth, self).up()

    def configure(self):
        config = self._dev_config
        exec_cmd("ethtool -A %s rx off tx off" % config["name"],
                 die_on_err=False, log_outputs=False)

        hw_addr = self._convert_hwaddr(config)

        s_ipv4, s_ipv6 = self._nm_make_ip_settings(config["addresses"])

        s_eth = dbus.Dictionary({'mac-address': hw_addr}, signature='sv')
        s_con = dbus.Dictionary({
            'type': '802-3-ethernet',
            'autoconnect': dbus.Boolean(False),
            'uuid': str(uuid.uuid4()),
            'id': 'lnst_ethcon'}, signature='sv')

        connection = dbus.Dictionary({
            '802-3-ethernet': s_eth,
            'connection': s_con,
            'ipv4': s_ipv4,
            'ipv6': s_ipv6}, signature='sa{sv}')

        self._connection = connection
        self._nm_add_connection()

    def deconfigure(self):
        if self._con_obj_path != None:
            self._nm_rm_connection()

class NmConfigDeviceBond(NmConfigDeviceGeneric):
    _modulename = "bonding"
    _moduleparams = "max_bonds=0"

    @classmethod
    def is_nm_managed(cls, dev_config, if_manager):
        if _dev_exists(dev_config["hwaddr"]):
            managed = super(NmConfigDeviceBond, cls).is_nm_managed(dev_config,
                                                                   if_manager)
        else:
            slave_dev = if_manager.get_mapped_device(get_slaves(dev_config)[0])
            slave_config = slave_dev.get_conf_dict()
            managed = is_nm_managed(slave_config, if_manager)

        for slave_id in get_slaves(dev_config):
            slave_dev = if_manager.get_mapped_device(slave_id)
            slave_config = slave_dev.get_conf_dict()
            if is_nm_managed(slave_config, if_manager) != managed:
                msg = "Mixing NM managed and not managed devices in a "\
                        "master-slave relationship is not allowed!"
                raise Exception(msg)

        return managed

    def up(self):
        super(NmConfigDeviceBond, self).up()

    def down(self):
        for slave_id in get_slaves(self._dev_config):
            slave_dev = self._if_manager.get_mapped_device(slave_id)
            slave_dev.down()

        super(NmConfigDeviceBond, self).down()

    def _setup_options(self):
        if not "options" in self._dev_config:
            return dbus.Dictionary({}, signature="ss")
        options = {}
        for option, value in self._dev_config["options"]:
            if option == "primary":
                '''
                "primary" option is not direct value but it's
                index of netdevice. So take the appropriate name from config
                '''
                slave_dev = self._if_manager.get_mapped_device(int(value))
                value = slave_dev.get_name()
            options[option] = value
        if options:
            return dbus.Dictionary(options, signature="ss")
        else:
            return None

    def _add_bond(self):
        config = self._dev_config
        config["master_uuid"] = str(uuid.uuid4())

        s_bond_con = dbus.Dictionary({
            'type': 'bond',
            'autoconnect': dbus.Boolean(False),
            'uuid': config["master_uuid"],
            'id': config["name"]+"_con"})

        options = self._setup_options()

        if options:
            s_bond = dbus.Dictionary({
                'interface-name': config["name"],
                'options': options})
        else:
            s_bond = dbus.Dictionary({
                'interface-name': config["name"]})

        s_ipv4, s_ipv6 = self._nm_make_ip_settings(config["addresses"])

        connection = dbus.Dictionary({
            'bond': s_bond,
            'ipv4': s_ipv4,
            'ipv6': s_ipv6,
            'connection': s_bond_con})

        self._connection = connection
        self._nm_add_connection()

    def _rm_bond(self):
        if self._con_obj_path != None:
            self._nm_rm_connection()

        #older versions of NM don't know how to remove soft devices...
        if get_nm_version() < "0.9.9":
            try:
                bond_masters = "/sys/class/net/bonding_masters"
                exec_cmd('echo "-%s" > %s' % (config["name"], bond_masters))
            except:
                pass

    def _add_slaves(self):
        for slave_id in get_slaves(self._dev_config):
            slave_dev = self._if_manager.get_mapped_device(slave_id)
            slave_config = slave_dev.get_configuration()
            slave_config.nm_enslave("bond", self._dev_config["master_uuid"], {})

    def _rm_slaves(self):
        for slave_id in get_slaves(self._dev_config):
            slave_dev = self._if_manager.get_mapped_device(slave_id)
            slave_config = slave_dev.get_configuration()
            slave_config.nm_free()

    def configure(self):
        self._add_bond()
        self._add_slaves()

    def deconfigure(self):
        self._rm_slaves()
        self._rm_bond()

class NmConfigDeviceBridge(NmConfigDeviceGeneric):
    _modulename = "bridge"

    @classmethod
    def is_nm_managed(cls, dev_config, if_manager):
        if _dev_exists(dev_config["hwaddr"]):
            managed = super(NmConfigDeviceBridge, cls).is_nm_managed(dev_config,
                                                                     if_manager)
        else:
            slave_dev = if_manager.get_mapped_device(get_slaves(dev_config)[0])
            slave_config = slave_dev.get_conf_dict()
            managed = is_nm_managed(slave_config, if_manager)

        for slave_id in get_slaves(dev_config):
            slave_dev = if_manager.get_mapped_device(slave_id)
            slave_config = slave_dev.get_conf_dict()
            if is_nm_managed(slave_config, if_manager) != managed:
                msg = "Mixing NM managed and not managed devices in a "\
                        "master-slave relationship is not allowed!"
                raise Exception(msg)

        return managed

    def up(self):
        super(NmConfigDeviceBridge, self).up()

    def down(self):
        for slave_id in get_slaves(self._dev_config):
            slave_dev = self._if_manager.get_mapped_device(slave_id)
            slave_dev.down()

        super(NmConfigDeviceBridge, self).down()

    def _add_bridge(self):
        config = self._dev_config
        config["master_uuid"] = str(uuid.uuid4())

        s_bridge_con = dbus.Dictionary({
            'type': 'bridge',
            'autoconnect': dbus.Boolean(False),
            'uuid': config["master_uuid"],
            'id': config["name"]+"_con"})

        s_bridge = dbus.Dictionary({
            'interface-name': config["name"],
            'stp': dbus.Boolean(False)})

        s_ipv4, s_ipv6 = self._nm_make_ip_settings(config["addresses"])

        connection = dbus.Dictionary({
            'bridge': s_bridge,
            'ipv4': s_ipv4,
            'ipv6': s_ipv6,
            'connection': s_bridge_con})

        self._connection = connection
        self._nm_add_connection()

    def _rm_bridge(self):
        if self._con_obj_path != None:
            self._nm_rm_connection()

        #older versions of NM don't know how to remove soft devices...
        if get_nm_version() < "0.9.9":
            try:
                exec_cmd("ip link set %s down" % config["name"])
                exec_cmd("brctl delbr %s " % config["name"])
            except:
                pass

    def _add_slave(self, slave_id):
        slave_dev = self._if_manager.get_mapped_device(slave_id)
        slave_config = slave_dev.get_configuration()
        slave_config.nm_enslave("bridge", self._dev_config["master_uuid"], {})

    def _rm_slave(self, slave_id):
        slave_dev = self._if_manager.get_mapped_device(slave_id)
        slave_config = slave_dev.get_configuration()
        slave_config.nm_free()

    def _add_slaves(self):
        for slave_id in get_slaves(self._dev_config):
            self._add_slave(slave_id)

    def _rm_slaves(self):
        for slave_id in get_slaves(self._dev_config):
            self._rm_slave(slave_id)

    def configure(self):
        self._add_bridge()
        self._add_slaves()

    def deconfigure(self):
        self._rm_slaves()
        self._rm_bridge()

    def slave_add(self, slave_id):
        self._add_slave(slave_id)

    def slave_del(self, slave_id):
        self._rm_slave(slave_id)

class NmConfigDeviceMacvlan(NmConfigDeviceGeneric):
    #Not supported by NetworkManager yet
    @classmethod
    def is_nm_managed(cls, dev_config, if_manager):
        managed = False

        for slave_id in get_slaves(dev_config):
            slave_dev = if_manager.get_mapped_device(slave_id)
            slave_config = slave_dev.get_conf_dict()
            if is_nm_managed(slave_config, if_manager) != managed:
                msg = "Mixing NM managed and not managed devices in a "\
                        "master-slave relationship is not allowed!"
                raise Exception(msg)

        return managed

class NmConfigDeviceVlan(NmConfigDeviceGeneric):
    _modulename = "8021q"

    @classmethod
    def is_nm_managed(cls, dev_config, if_manager):
        if _dev_exists(dev_config["hwaddr"]):
            managed = super(NmConfigDeviceVlan, cls).is_nm_managed(dev_config,
                                                                   if_manager)
        else:
            slave_dev = if_manager.get_mapped_device(get_slaves(dev_config)[0])
            slave_config = slave_dev.get_conf_dict()
            managed = is_nm_managed(slave_config, if_manager)

        for slave_id in get_slaves(dev_config):
            slave_dev = if_manager.get_mapped_device(slave_id)
            slave_config = slave_dev.get_conf_dict()
            if is_nm_managed(slave_config, if_manager) != managed:
                msg = "Mixing NM managed and not managed devices in a "\
                        "master-slave relationship is not allowed!"
                raise Exception(msg)

        return managed

    def _check_ip_link_add(self):
        output = exec_cmd("ip link help", die_on_err=False,
                          log_outputs=False)[1]
        for line in output.split("\n"):
            if re.match(r'^.*ip link add [\[]{0,1}link.*$', line):
                return True
        return False

    def _get_vlan_info(self):
        config = self._dev_config;
        realdev = self._if_manager.get_mapped_device(get_slaves(config)[0])
        realdev_name = realdev.get_name()
        dev_name = config["name"]
        vlan_tci = int(get_option(config, "vlan_tci"))
        return dev_name, realdev_name, vlan_tci

    def configure(self):
        config = self._dev_config

        dev_name, realdev, vlan_tci = self._get_vlan_info()

        s_vlan_con = dbus.Dictionary({
            'type': 'vlan',
            'autoconnect': dbus.Boolean(False),
            'uuid': str(uuid.uuid4()),
            'id': dev_name+"_con"})

        s_vlan = dbus.Dictionary({
            'interface-name': dev_name,
            'parent': realdev,
            'id': dbus.UInt32(vlan_tci)}, signature="sv")

        s_ipv4, s_ipv6 = self._nm_make_ip_settings(config["addresses"])

        connection = dbus.Dictionary({
            'vlan': s_vlan,
            'ipv4': s_ipv4,
            'ipv6': s_ipv6,
            'connection': s_vlan_con})

        self._connection = connection
        self._nm_add_connection()

    def deconfigure(self):
        if self._con_obj_path != None:
            self._nm_rm_connection()

        #older versions of NM don't know how to remove soft devices...
        #and lnst will break when multiple devices with the same mac exist
        if get_nm_version() < "0.9.9":
            try:
                dev_name = self._get_vlan_info()[0]
                if self._check_ip_link_add():
                    exec_cmd("ip link del %s" % dev_name)
                else:
                    exec_cmd("vconfig rem %s" % dev_name)
            except:
                pass

    def up(self):
        realdev_id = get_slaves(self._dev_config)[0]
        realdev = self._if_manager.get_mapped_device(realdev_id)
        realdev.up()

        super(NmConfigDeviceVlan, self).up()

class NmConfigDeviceTeam(NmConfigDeviceGeneric):
    @classmethod
    def is_nm_managed(cls, dev_config, if_manager):
        if _dev_exists(dev_config["hwaddr"]):
            managed = super(NmConfigDeviceTeam, cls).is_nm_managed(dev_config,
                                                                   if_manager)
        else:
            if get_nm_version() < "0.9.9":
                managed = False
            else:
                slave_dev = if_manager.get_mapped_device(get_slaves(dev_config)[0])
                slave_config = slave_dev.get_conf_dict()
                managed = is_nm_managed(slave_config, if_manager)

        for slave_id in get_slaves(dev_config):
            slave_dev = if_manager.get_mapped_device(slave_id)
            slave_config = slave_dev.get_conf_dict()
            if is_nm_managed(slave_config, if_manager) != managed:
                msg = "Mixing NM managed and not managed devices in a "\
                        "master-slave relationship is not allowed!"
                raise Exception(msg)

        return managed

    def up(self):
        super(NmConfigDeviceTeam, self).up()

    def down(self):
        for slave_id in get_slaves(self._dev_config):
            slave_dev = self._if_manager.get_mapped_device(slave_id)
            slave_dev.down()

        super(NmConfigDeviceTeam, self).down()

    def _add_team(self):
        config = self._dev_config
        config["master_uuid"] = str(uuid.uuid4())

        s_team_con = dbus.Dictionary({
            'type': 'team',
            'autoconnect': dbus.Boolean(False),
            'uuid': config["master_uuid"],
            'id': config["name"]+"_con"})

        teamd_config = get_option(config, "teamd_config")

        s_team = dbus.Dictionary({
            'interface-name': config["name"],
            'config': teamd_config})

        s_ipv4, s_ipv6 = self._nm_make_ip_settings(config["addresses"])

        connection = dbus.Dictionary({
            'team': s_team,
            'ipv4': s_ipv4,
            'ipv6': s_ipv6,
            'connection': s_team_con})

        self._connection = connection
        self._nm_add_connection()

    def _rm_team(self):
        if self._con_obj_path != None:
            self._nm_rm_connection()

    def _add_slaves(self):
        for slave_id in get_slaves(self._dev_config):
            slave_dev = self._if_manager.get_mapped_device(slave_id)
            slave_config = slave_dev.get_configuration()

            teamd_port_config = get_slave_option(self._dev_config,
                                                 slave_id,
                                                 "teamd_port_config")

            slave_con = dbus.Dictionary()

            if teamd_port_config != None:
                s_port_cfg = dbus.Dictionary({
                    'config': teamd_port_config})
                slave_con['team-port'] = s_port_cfg

            slave_config.nm_enslave("team", self._dev_config["master_uuid"],
                                    slave_con)

    def _rm_slaves(self):
        for slave_id in get_slaves(self._dev_config):
            slave_dev = self._if_manager.get_mapped_device(slave_id)
            slave_config = slave_dev.get_configuration()
            slave_config.nm_free()

    def configure(self):
        self._add_team()
        self._add_slaves()

    def deconfigure(self):
        self._rm_slaves()
        self._rm_team()

class NmConfigDeviceOvsBridge(NmConfigDeviceGeneric):
    #Not supported by NetworkManager
    @classmethod
    def is_nm_managed(cls, dev_config, if_manager):
        managed = False

        for slave_id in get_slaves(dev_config):
            slave_dev = if_manager.get_mapped_device(slave_id)
            slave_config = slave_dev.get_conf_dict()
            if is_nm_managed(slave_config, if_manager) != managed:
                msg = "Mixing NM managed and not managed devices in a "\
                        "master-slave relationship is not allowed!"
                raise Exception(msg)

        return managed

class NmConfigDeviceVEth(NmConfigDeviceGeneric):
    #Not supported by NetworkManager
    @classmethod
    def is_nm_managed(cls, dev_config, if_manager):
        return False

class NmConfigDeviceVti(NmConfigDeviceGeneric):
    #Not supported by NetworkManager
    @classmethod
    def is_nm_managed(cls, dev_config, if_manager):
        return False

type_class_mapping = {
    "eth": NmConfigDeviceEth,
    "bond": NmConfigDeviceBond,
    "bridge": NmConfigDeviceBridge,
    "macvlan": NmConfigDeviceMacvlan,
    "vlan": NmConfigDeviceVlan,
    "team": NmConfigDeviceTeam,
    "ovs_bridge": NmConfigDeviceOvsBridge,
    "veth": NmConfigDeviceVEth,
   "vti": NmConfigDeviceVti
}

def is_nm_managed(dev_config, if_manager):
    if lnst_config.get_option("environment", "use_nm") and\
       check_process_running("NetworkManager"):
        return type_class_mapping[dev_config["type"]].is_nm_managed(dev_config,
                                                                    if_manager)
    else:
        return False
