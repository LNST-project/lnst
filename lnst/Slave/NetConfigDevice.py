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
from lnst.Common.ExecCmd import exec_cmd
from lnst.Slave.NetConfigCommon import get_slaves, get_option, get_slave_option
from lnst.Common.Utils import kmod_in_use, bool_it
from lnst.Slave.NmConfigDevice import type_class_mapping as nm_type_class_mapping
from lnst.Common.Utils import check_process_running


class NetConfigDeviceGeneric:
    '''
    Generic class for device manipulation all type classes should
    extend this one.
    '''
    _modulename = ""
    _moduleload = True
    _moduleparams = ""
    _cleanupcmd = ""

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
        if self._modulename and self._moduleload:
            exec_cmd("modprobe %s %s" % (self._modulename, self._moduleparams))

    @classmethod
    def type_cleanup(self):
        if self._cleanupcmd:
            exec_cmd(self._cleanupcmd, die_on_err=False)
        if self._modulename:
            kmod_in_use(self._modulename, 300)
            exec_cmd("modprobe -q -r %s" % self._modulename, die_on_err=False)

class NetConfigDeviceEth(NetConfigDeviceGeneric):
    def configure(self):
        netdev = self._netdev
        exec_cmd("ip addr flush %s" % netdev["name"])
        exec_cmd("ethtool -A %s rx off tx off" % netdev["name"], die_on_err=False, log_outputs=False)

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

def prepare_json_str(json_str):
    if not json_str:
        return ""
    json_str = json_str.replace('"', '\\"')
    json_str = re.sub('\s+', ' ', json_str)
    return json_str

class NetConfigDeviceTeam(NetConfigDeviceGeneric):
    _pidfile = None
    _modulename = "team_mode_roundrobin team_mode_activebackup team_mode_broadcast team_mode_loadbalance team"
    _moduleload = False
    _cleanupcmd = "killall -q teamd"

    def _should_enable_dbus(self):
        dbus_disabled = get_option(self._netdev, "dbus_disabled")
        if not dbus_disabled or bool_it(dbus_disabled):
            return True
        return False

    def _ports_down(self):
        for slave_id in get_slaves(self._netdev):
            port_netdev = self._config[slave_id]
            NetConfigDevice(port_netdev, self._config).down()

    def _ports_up(self):
        for slave_id in get_slaves(self._netdev):
            port_netdev = self._config[slave_id]
            NetConfigDevice(port_netdev, self._config).up()

    def configure(self):
        self._ports_down()

        teamd_config = get_option(self._netdev, "teamd_config")
        teamd_config = prepare_json_str(teamd_config)

        dev_name = self._netdev["name"]
        pidfile = "/var/run/teamd_%s.pid" % dev_name

        dbus_option = " -D" if self._should_enable_dbus() else ""
        exec_cmd("teamd -r -d -c \"%s\" -t %s -p %s%s" % (teamd_config, dev_name, pidfile, dbus_option))

        self._pidfile = pidfile

        for slave_id in get_slaves(self._netdev):
            self.slave_add(slave_id)
        self._ports_up()

    def deconfigure(self):
        for slave_id in get_slaves(self._netdev):
            self.slave_del(slave_id)

        dev_name = self._netdev["name"]
        pidfile = "/var/run/teamd_%s.pid" % dev_name

        exec_cmd("teamd -k -p %s" % pidfile)

    def slave_add(self, slaveid):
        dev_name = self._netdev["name"]
        port_netdev = self._config[slaveid]
        port_name = port_netdev["name"]
        teamd_port_config = get_slave_option(self._netdev,
                                             slaveid, "teamd_port_config")
        dbus_option = "-D" if self._should_enable_dbus() else ""
        if teamd_port_config:
            teamd_port_config = prepare_json_str(teamd_port_config)
            exec_cmd("teamdctl %s %s port config update %s \"%s\"" % (dbus_option, dev_name, port_name, teamd_port_config))
        NetConfigDevice(port_netdev, self._config).down()
        exec_cmd("teamdctl %s %s port add %s" % (dbus_option, dev_name, port_name))

    def slave_del(self, slaveid):
        dev_name = self._netdev["name"]
        port_name = self._config[slaveid]["name"]
        dbus_option = "-D" if self._should_enable_dbus() else ""
        exec_cmd("teamdctl %s %s port remove %s" % (dbus_option, dev_name, port_name))

type_class_mapping = {
    "eth": NetConfigDeviceEth,
    "bond": NetConfigDeviceBond,
    "bridge": NetConfigDeviceBridge,
    "macvlan": NetConfigDeviceMacvlan,
    "vlan": NetConfigDeviceVlan,
    "team": NetConfigDeviceTeam
}

def NetConfigDevice(netdev, config, lnst_config):
    '''
    Class dispatcher
    '''
    if check_process_running("NetworkManager") and \
       lnst_config.get_option("environment", "use_nm"):
        return nm_type_class_mapping[netdev["type"]](netdev, config)
    else:
        return type_class_mapping[netdev["type"]](netdev, config)

def NetConfigDeviceType(dev_type, lnst_config):
    '''
    Class dispatcher for classmethods
    '''
    if check_process_running("NetworkManager") and \
       lnst_config.get_option("environment", "use_nm"):
        return nm_type_class_mapping[dev_type]
    else:
        return type_class_mapping[dev_type]

def NetConfigDeviceAllCleanup(lnst_config):
    if check_process_running("NetworkManager") and \
       lnst_config.get_option("environment", "use_nm"):
        for dev_type in nm_type_class_mapping:
            NetConfigDeviceType(dev_type).type_cleanup()
    else:
        for dev_type in type_class_mapping:
            NetConfigDeviceType(dev_type).type_cleanup()
