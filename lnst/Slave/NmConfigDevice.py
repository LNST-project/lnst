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
from gi.repository import NetworkManager, GObject
from lnst.Common.ExecCmd import exec_cmd
from lnst.Slave.NetConfigCommon import get_slaves, get_option, get_slave_option
from lnst.Common.Utils import kmod_in_use, bool_it

NM_BUS = "org.freedesktop.NetworkManager"
OBJ_PRE = "/org/freedesktop/NetworkManager"
IF_PRE = NM_BUS

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


    def __init__(self, netdev, config):
        self._netdev = netdev
        self._config = config
        self._bus = dbus.SystemBus()
        self._nm_obj = self._bus.get_object(NM_BUS, OBJ_PRE)
        self._nm_if = dbus.Interface(self._nm_obj, IF_PRE)

    def configure(self):
        pass

    def deconfigure(self):
        pass

    def slave_add(self, slaveid):
        pass

    def slave_del(self, slaveid):
        pass

    def up(self):
        netdev = self._netdev
        self._nm_activate_connection(netdev)

    def down(self):
        netdev = self._netdev
        self._nm_deactivate_connection(netdev)

    @classmethod
    def type_init(self):
        pass

    @classmethod
    def type_cleanup(self):
        pass

    def _wait_for_state(self, new_state, old_state, reason):
        self._device_state = new_state
        if self._device_state == self._wait_for:
            self._loop.quit()

    def _poll_loop(self, func, expected_val, *args):
        while True:
            if func(*args) == expected_val:
                break
            time.sleep(1)

    def _convert_hwaddr(self, netdev):
        if "hwaddr" in netdev:
            hwaddr = netdev["hwaddr"]
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

    def _nm_add_connection(self, connection):
        bus = self._bus
        settings_obj = bus.get_object(NM_BUS, OBJ_PRE + "/Settings")
        settings_if = dbus.Interface(settings_obj, IF_PRE + ".Settings")
        con_obj_path = settings_if.AddConnection(connection)
        logging.debug("Added NM connection: %s" % con_obj_path)
        return con_obj_path

    def _nm_rm_connection(self, con_obj_path):
        bus = self._bus
        con_obj = bus.get_object(NM_BUS, con_obj_path)
        con_if = dbus.Interface(con_obj, IF_PRE + ".Settings.Connection")
        con_if.Delete()
        logging.debug("Removed NM connection: %s" % con_obj_path)

    def _nm_activate_connection(self, netdev):
        if "acon_obj_path" in netdev and netdev["acon_obj_path"] != "" or\
           "con_obj_path" not in netdev:
            return
        else:
            logging.info("Activating connection on interface %s"
                                                    % netdev["name"])
            bus = self._bus
            nm_if = self._nm_if

            try:
                device_obj_path = nm_if.GetDeviceByIpIface(netdev["name"])
            except:
                device_obj_path = "/"

            netdev["acon_obj_path"] = nm_if.ActivateConnection(
                                                netdev["con_obj_path"],
                                                device_obj_path, "/")

            logging.debug("Device object path: %s" % device_obj_path)
            logging.debug("Connection object path: %s" % netdev["con_obj_path"])
            logging.debug("Active connection object path: %s"
                                                % netdev["acon_obj_path"])

            act_con = bus.get_object(NM_BUS, netdev["acon_obj_path"])
            act_con_props = dbus.Interface(act_con,
                                           "org.freedesktop.DBus.Properties")
            self._poll_loop(act_con_props.Get,
                            NetworkManager.ActiveConnectionState.ACTIVATED,
                            IF_PRE + ".Connection.Active", "State")

    def _nm_deactivate_connection(self, netdev):
        if "acon_obj_path" not in netdev or netdev["acon_obj_path"] == "":
            return
        else:
            logging.info("Deactivating connection on device %s"
                                                    % netdev["name"])
            logging.debug("Active connection object path: %s"
                                                    % netdev["acon_obj_path"])
            self._nm_if.DeactivateConnection(netdev["acon_obj_path"])
            netdev["acon_obj_path"] = ""

class NmConfigDeviceEth(NmConfigDeviceGeneric):
    def up(self):
        netdev = self._netdev

        bus = self._bus
        nm_if = self._nm_if

        device_obj_path = nm_if.GetDeviceByIpIface(netdev["name"])

        dev = bus.get_object(NM_BUS, device_obj_path)
        dev_props = dbus.Interface(dev, "org.freedesktop.DBus.Properties")

        state = dev_props.Get(IF_PRE + ".Device", "State")
        if state == NetworkManager.DeviceState.UNAVAILABLE:
            logging.info("Resetting interface so NM manages it.")
            exec_cmd("ip link set %s down" % netdev["name"])
            exec_cmd("ip link set %s up" % netdev["name"])

            self._poll_loop(dev_props.Get,
                            NetworkManager.DeviceState.DISCONNECTED,
                            IF_PRE + ".Device", "State")

        super(NmConfigDeviceEth, self).up()

    def configure(self):
        netdev = self._netdev
        exec_cmd("ethtool -A %s rx off tx off" % netdev["name"], die_on_err=False, log_outputs=False)

        hw_addr = self._convert_hwaddr(netdev)

        s_ipv4, s_ipv6 = self._nm_make_ip_settings(netdev["addresses"])

        #TODO is this correct?? NM sets ipv4 to automatic if both are disabled
        if s_ipv4["method"] == "disabled" and s_ipv6["method"] == "ignore":
            return

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

        netdev["con_obj_path"] = self._nm_add_connection(connection)

    def deconfigure(self):
        netdev = self._netdev
        if "con_obj_path" in netdev and netdev["con_obj_path"] != "":
            self._nm_rm_connection(netdev["con_obj_path"])
            netdev["con_obj_path"] = ""

class NmConfigDeviceBond(NmConfigDeviceGeneric):
    _modulename = "bonding"
    _moduleparams = "max_bonds=0"

    def up(self):
        super(NmConfigDeviceBond, self).up()

        for slave in get_slaves(self._netdev):
            netdev = self._config[slave]
            self._nm_activate_connection(netdev)

    def down(self):
        for slave in get_slaves(self._netdev):
            netdev = self._config[slave]
            self._nm_deactivate_connection(netdev)

        super(NmConfigDeviceBond, self).down()

    def _setup_options(self):
        if not "options" in self._netdev:
            return dbus.Dictionary({}, signature="ss")
        options = {}
        for option, value in self._netdev["options"]:
            if option == "primary":
                '''
                "primary" option is not direct value but it's
                index of netdevice. So take the appropriate name from config
                '''
                value = self._config[int(value)]["name"]
            options[option] = value
        return dbus.Dictionary(options, signature="ss")

    def _add_bond(self):
        netdev = self._netdev
        netdev["master_uuid"] = str(uuid.uuid4())

        s_bond_con = dbus.Dictionary({
            'type': 'bond',
            'autoconnect': dbus.Boolean(False),
            'uuid': netdev["master_uuid"],
            'id': netdev["name"]+"_con"})

        options = self._setup_options()

        s_bond = dbus.Dictionary({
            'interface-name': netdev["name"],
            'options': options})

        s_ipv4, s_ipv6 = self._nm_make_ip_settings(netdev["addresses"])

        connection = dbus.Dictionary({
            'bond': s_bond,
            'ipv4': s_ipv4,
            'ipv6': s_ipv6,
            'connection': s_bond_con})

        netdev["con_obj_path"] = self._nm_add_connection(connection)

    def _rm_bond(self):
        netdev = self._netdev
        if netdev["con_obj_path"] != "":
            self._nm_rm_connection(netdev["con_obj_path"])
            netdev["con_obj_path"] = ""

        #NM doesn't know how to remove soft devices...
        bond_masters = "/sys/class/net/bonding_masters"
        exec_cmd('echo "-%s" > %s' % (netdev["name"], bond_masters))

    def _add_slaves(self):
        for slave in get_slaves(self._netdev):
            netdev = self._config[slave]
            slave_name = netdev["name"]

            hw_addr = self._convert_hwaddr(netdev)

            s_eth = dbus.Dictionary({
                'duplex': dbus.Array('full', 's'),
                'mac-address': hw_addr})

            s_slave_con = dbus.Dictionary({
                'type': '802-3-ethernet',
                'autoconnect': dbus.Boolean(False),
                'uuid': str(uuid.uuid4()),
                'id': 'slave_con',
                'master': self._netdev["master_uuid"],
                'slave-type': 'bond'})

            slave_con = dbus.Dictionary({
                '802-3-ethernet': s_eth,
                'connection': s_slave_con})

            netdev["con_obj_path"] = self._nm_add_connection(slave_con)

    def _rm_slaves(self):
        for slave in get_slaves(self._netdev):
            netdev = self._config[slave]
            if netdev["con_obj_path"] != "":
                self._nm_rm_connection(netdev["con_obj_path"])
                netdev["con_obj_path"] = ""

    def configure(self):
        self._add_bond()
        self._add_slaves()

    def deconfigure(self):
        self._rm_slaves()
        self._rm_bond()

class NmConfigDeviceBridge(NmConfigDeviceGeneric):
    _modulename = "bridge"

    def up(self):
        super(NmConfigDeviceBridge, self).up()

        for slave in get_slaves(self._netdev):
            netdev = self._config[slave]
            self._nm_activate_connection(netdev)

    def down(self):
        for slave in get_slaves(self._netdev):
            netdev = self._config[slave]
            self._nm_deactivate_connection(netdev)

        super(NmConfigDeviceBridge, self).down()

    def _add_bridge(self):
        netdev = self._netdev
        netdev["master_uuid"] = str(uuid.uuid4())

        s_bridge_con = dbus.Dictionary({
            'type': 'bridge',
            'autoconnect': dbus.Boolean(False),
            'uuid': netdev["master_uuid"],
            'id': netdev["name"]+"_con"})

        s_bridge = dbus.Dictionary({
            'interface-name': netdev["name"],
            'stp': dbus.Boolean(False)})

        s_ipv4, s_ipv6 = self._nm_make_ip_settings(netdev["addresses"])

        connection = dbus.Dictionary({
            'bridge': s_bridge,
            'ipv4': s_ipv4,
            'ipv6': s_ipv6,
            'connection': s_bridge_con})

        netdev["con_obj_path"] = self._nm_add_connection(connection)

    def _rm_bridge(self):
        netdev = self._netdev
        if netdev["con_obj_path"] != "":
            self._nm_rm_connection(netdev["con_obj_path"])
            netdev["con_obj_path"] = ""

        #NM doesn't know how to remove soft devices...
        exec_cmd("ip link set %s down" % netdev["name"])
        exec_cmd("brctl delbr %s " % netdev["name"])

    def _add_slave(self, slave):
        netdev = self._config[slave]
        slave_name = netdev["name"]

        hw_addr = self._convert_hwaddr(netdev)

        s_eth = dbus.Dictionary({
            'duplex': dbus.Array('full', 's'),
            'mac-address': hw_addr})

        s_slave_con = dbus.Dictionary({
            'type': '802-3-ethernet',
            'autoconnect': dbus.Boolean(False),
            'uuid': str(uuid.uuid4()),
            'id': 'slave_con',
            'master': self._netdev["master_uuid"],
            'slave-type': 'bridge'})

        slave_con = dbus.Dictionary({
            '802-3-ethernet': s_eth,
            'connection': s_slave_con})

        netdev["con_obj_path"] = self._nm_add_connection(slave_con)

    def _rm_slave(self, slave):
        netdev = self._config[slave]
        if netdev["con_obj_path"] != "":
            self._nm_rm_connection(netdev["con_obj_path"])
            netdev["con_obj_path"] = ""

    def _add_slaves(self):
        for slaveid in get_slaves(self._netdev):
            self._add_slave(slaveid)

    def _rm_slaves(self):
        for slaveid in get_slaves(self._netdev):
            self._rm_slave(slaveid)

    def configure(self):
        self._add_bridge()
        self._add_slaves()

    def deconfigure(self):
        self._rm_slaves()
        self._rm_bridge()

    def slave_add(self, slaveid):
        self._add_slave(slaveid)

    def slave_del(self, slaveid):
        self._rm_slave(slaveid)

class NmConfigDeviceMacvlan(NmConfigDeviceGeneric):
    #Not supported by NetworkManager yet
    pass

class NmConfigDeviceVlan(NmConfigDeviceGeneric):
    _modulename = "8021q"

    def _check_ip_link_add(self):
        output = exec_cmd("ip link help", die_on_err=False,
                          log_outputs=False)[1]
        for line in output.split("\n"):
            if re.match(r'^.*ip link add [\[]{0,1}link.*$', line):
                return True
        return False

    def _get_vlan_info(self):
        netdev = self._netdev;
        realdev_index = get_slaves(netdev)[0]
        realdev = self._config[realdev_index]["name"]
        dev_name = netdev["name"]
        vlan_tci = int(get_option(netdev, "vlan_tci"))
        return dev_name, realdev, vlan_tci

    def configure(self):
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

        s_ipv4, s_ipv6 = self._nm_make_ip_settings(self._netdev["addresses"])

        connection = dbus.Dictionary({
            'vlan': s_vlan,
            'ipv4': s_ipv4,
            'ipv6': s_ipv6,
            'connection': s_vlan_con})

        self._netdev["con_obj_path"] = self._nm_add_connection(connection)

    def deconfigure(self):
        netdev = self._netdev
        if "con_obj_path" in netdev and netdev["con_obj_path"] != "":
            self._nm_rm_connection(netdev["con_obj_path"])
            netdev["con_obj_path"] = ""

        #NM doesn't know how to remove soft devices...
        #and lnst will break when multiple devices with the same mac exist
        dev_name = self._get_vlan_info()[0]
        if self._check_ip_link_add():
            exec_cmd("ip link del %s" % dev_name)
        else:
            exec_cmd("vconfig rem %s" % dev_name)

class NmConfigDeviceTeam(NmConfigDeviceGeneric):
    #Not supported by NetworkManager yet
    pass

type_class_mapping = {
    "eth": NmConfigDeviceEth,
    "bond": NmConfigDeviceBond,
    "bridge": NmConfigDeviceBridge,
    "macvlan": NmConfigDeviceMacvlan,
    "vlan": NmConfigDeviceVlan,
    "team": NmConfigDeviceTeam
}
