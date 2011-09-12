"""
This module defines multiple classes useful for configuring
multiple types of net devices

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import logging
import re
import sys
from Common.ExecCmd import exec_cmd
from NetConfigCommon import get_slaves, get_option

class NetConfigDeviceGeneric:
    '''
    Generic class for device manipulation all type classes should
    extend this one.
    '''
    _modulename = ""
    _moduleparams = ""

    def __init__(self, netdev, config):
        self._netdev = netdev
        self._config = config

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
        if "addresses" in netdev:
            for address in netdev["addresses"]:
                exec_cmd("ip addr add %s dev %s" % (address, netdev["name"]))
        exec_cmd("ip link set %s up" % netdev["name"])

    def down(self):
        netdev = self._netdev
        if "addresses" in netdev:
            for address in netdev["addresses"]:
                exec_cmd("ip addr del %s dev %s" % (address, netdev["name"]))
        exec_cmd("ip link set %s down" % netdev["name"])

    @classmethod
    def type_init(self):
        if self._modulename:
            exec_cmd("modprobe %s %s" % (self._modulename, self._moduleparams))

    @classmethod
    def type_cleanup(self):
        if self._modulename:
            exec_cmd("modprobe -r %s" % self._modulename, die_on_err=False)

    @classmethod
    def type_check(self):
        if self._modulename:
            output = exec_cmd("modprobe -l %s" % self._modulename)[0]
            for line in output.split("\n"):
                if re.match(r'^.*\/%s\.ko$' % self._modulename, line):
                    return True
        False

class NetConfigDeviceEth(NetConfigDeviceGeneric):
    def configure(self):
        netdev = self._netdev
        exec_cmd("ip addr flush %s" % netdev["name"])

class NetConfigDeviceBond(NetConfigDeviceGeneric):
    _modulename = "bonding"
    _moduleparams = "max_bonds=0"

    def _add_rm_bond(self, mark):
        bond_masters = "/sys/class/net/bonding_masters"
        exec_cmd('echo "%s%s" > %s' % (mark, self._netdev["name"],
                                       bond_masters))

    def _get_bond_dir(self):
        return "/sys/class/net/%s/bonding" % self._netdev["name"]

    def _setup_options(self):
        if not "options" in self._netdev:
            return
        options = self._netdev["options"]
        for option, value in options:
            if option == "primary":
                '''
                "primary" option is not direct value but it's
                index of netdevice. So take the appropriate name from config
                '''
                value = self._config[int(value)]["name"]
            exec_cmd('echo "%s" > %s/%s' % (value,
                                            self._get_bond_dir(),
                                            option))

    def _add_rm_slaves(self, mark):
        for slave in get_slaves(self._netdev):
            slavenetdev = self._config[slave]
            slave_name = slavenetdev["name"]
            if (mark == "+"):
                NetConfigDevice(slavenetdev, self._config).down()
            exec_cmd('echo "%s%s" > %s/slaves' % (mark, slave_name,
                                                  self._get_bond_dir()))

    def configure(self):
        self._add_rm_bond("+")
        self._setup_options()
        self._add_rm_slaves("+")

    def deconfigure(self):
        self._add_rm_slaves("-")
        self._add_rm_bond("-")

class NetConfigDeviceBridge(NetConfigDeviceGeneric):
    _modulename = "bridge"

    def _add_rm_bridge(self, prefix):
        exec_cmd("brctl %sbr %s " % (prefix, self._netdev["name"]))

    def _add_rm_port(self, prefix, slaveid):
        port_name = self._config[slaveid]["name"]
        exec_cmd("brctl %sif %s %s" % (prefix, self._netdev["name"],
                                       port_name))

    def _add_rm_ports(self, prefix):
        for slaveid in get_slaves(self._netdev):
            self._add_rm_port(prefix, slaveid)

    def configure(self):
        self._add_rm_bridge("add")
        self._add_rm_ports("add")

    def deconfigure(self):
        self._add_rm_ports("del")
        self._add_rm_bridge("del")

    def slave_add(self, slaveid):
        self._add_rm_port("add", slaveid)

    def slave_del(self, slaveid):
        self._add_rm_port("del", slaveid)

class NetConfigDeviceMacvlan(NetConfigDeviceGeneric):
    _modulename = "macvlan"

    def configure(self):
        netdev = self._netdev;
        realdev_index = netdev["slaves"][0]
        realdev = self._config[realdev_index]["name"]
        dev_name = netdev["name"]

        if "hwaddr" in netdev:
            hwaddr = " address %s" % netdev["hwaddr"]
        else:
            hwaddr = ""

        exec_cmd("ip link add link %s %s%s type macvlan"
                                    % (realdev, dev_name, hwaddr))

    def deconfigure(self):
        dev_name = self._netdev["name"]
        exec_cmd("ip link del %s" % dev_name)

class NetConfigDeviceVlan(NetConfigDeviceGeneric):
    _modulename = "8021q"

    def _check_ip_link_add(self):
        output = exec_cmd("ip link help", die_on_err=False,
                          log_outputs=False)[1]
        for line in output.split("\n"):
            if re.match(r'^.*ip link add link.*$', line):
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
        if self._check_ip_link_add():
            exec_cmd("ip link add link %s %s type vlan id %d"
                                    % (realdev, dev_name, vlan_tci))
        else:
            if not re.match(r'^%s.%d$' % (realdev, vlan_tci), dev_name):
                logging.error("Since using old vlan manipulation interface, "
                          "devname \"%s\" cannot be used" % dev_name)
                raise Exception("Bad vlan device name")
            exec_cmd("vconfig add %s %d" % (realdev, vlan_tci))

    def deconfigure(self):
        dev_name = self._get_vlan_info()[0]
        if self._check_ip_link_add():
            exec_cmd("ip link del %s" % dev_name)
        else:
            exec_cmd("vconfig rem %s" % dev_name)

type_class_mapping = {
    "eth": NetConfigDeviceEth,
    "bond": NetConfigDeviceBond,
    "bridge": NetConfigDeviceBridge,
    "macvlan": NetConfigDeviceMacvlan,
    "vlan": NetConfigDeviceVlan
}

def NetConfigDevice(netdev, config):
    '''
    Class dispatcher
    '''
    return type_class_mapping[netdev["type"]](netdev, config)

def NetConfigDeviceType(dev_type):
    '''
    Class dispatcher for classmethods
    '''
    return type_class_mapping[dev_type]

def NetConfigDeviceAllCleanup():
    for dev_type in type_class_mapping:
        if NetConfigDeviceType(dev_type).type_check():
            NetConfigDeviceType(dev_type).type_cleanup()
