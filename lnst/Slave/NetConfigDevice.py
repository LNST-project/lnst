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
from lnst.Slave.NetConfigCommon import get_slaves, get_option, get_slave_option, parse_netem
from lnst.Common.Utils import kmod_in_use, bool_it
from lnst.Slave.NmConfigDevice import type_class_mapping as nm_type_class_mapping
from lnst.Slave.NmConfigDevice import is_nm_managed
from lnst.Common.Utils import check_process_running
from lnst.Common.Config import lnst_config


class NetConfigDeviceGeneric(object):
    '''
    Generic class for device manipulation all type classes should
    extend this one.
    '''
    _modulename = ""
    _moduleload = True
    _moduleparams = ""
    _cleanupcmd = ""

    def __init__(self, dev_config, if_manager):
        self._dev_config = dev_config
        self._if_manager = if_manager
        self.type_init()

    def configure(self):
        pass

    def deconfigure(self):
        pass

    def slave_add(self, slave_id):
        pass

    def slave_del(self, slave_id):
        pass

    def create(self):
        pass

    def destroy(self):
        pass

    def up(self):
        config = self._dev_config
        if "addresses" in config:
            for address in config["addresses"]:
                exec_cmd("ip addr add %s dev %s" % (address, config["name"]))
        exec_cmd("ip link set %s up" % config["name"])

    def down(self):
        config = self._dev_config
        if "addresses" in config:
            for address in config["addresses"]:
                exec_cmd("ip addr del %s dev %s" % (address, config["name"]),
                         die_on_err=False)
        exec_cmd("ip link set %s down" % config["name"])

    @classmethod
    def type_init(self):
        if self._modulename and self._moduleload:
            exec_cmd("modprobe %s %s" % (self._modulename, self._moduleparams))

    @classmethod
    def type_cleanup(self):
        if self._cleanupcmd:
            exec_cmd(self._cleanupcmd, die_on_err=False)

class NetConfigDeviceEth(NetConfigDeviceGeneric):
    def configure(self):
        config = self._dev_config
        exec_cmd("ip addr flush %s" % config["name"])
        exec_cmd("ethtool -A %s rx off tx off" % config["name"], die_on_err=False, log_outputs=False)
        if config["netem"] is not None:
            cmd = "tc qdisc add dev %s root netem %s" % (config["name"], parse_netem(config["netem"]))
            exec_cmd(cmd)
            config["netem_cmd"] = cmd

    def deconfigure(self):
        config = self._dev_config
        if "netem_cmd" in config:
            exec_cmd(config["netem_cmd"].replace("add", "del"))

class NetConfigDeviceLoopback(NetConfigDeviceGeneric):
    def configure(self):
        config = self._dev_config

class NetConfigDeviceBond(NetConfigDeviceGeneric):
    _modulename = "bonding"
    _moduleparams = "max_bonds=0"

    def _add_rm_bond(self, mark):
        bond_masters = "/sys/class/net/bonding_masters"
        exec_cmd('echo "%s%s" > %s' % (mark, self._dev_config["name"],
                                       bond_masters))

    def _get_bond_dir(self):
        return "/sys/class/net/%s/bonding" % self._dev_config["name"]

    def _setup_options(self):
        if not "options" in self._dev_config:
            return
        options = self._dev_config["options"]

        #Make sure that the device is down before configuring options
        #this is a temporary workaround for NM setting the device IFF_UP on
        #creation, which means that there is still a race condition here.
        #Related to RH bgz #1114685
        exec_cmd('ip link set %s down' % self._dev_config["name"])

        for option, value in options:
            if option == "primary":
                '''
                "primary" option is not direct value but it's
                index of netdevice. So take the appropriate name from config
                '''
                slave_dev = self._if_manager.get_mapped_device(value)
                value = slave_dev.get_name()
            exec_cmd('echo "%s" > %s/%s' % (value,
                                            self._get_bond_dir(),
                                            option))

    def _add_rm_slaves(self, mark):
        for slave_id in get_slaves(self._dev_config):
            slave_dev = self._if_manager.get_mapped_device(slave_id)
            slave_conf = slave_dev.get_conf_dict()
            slave_name = slave_dev.get_name()
            if mark == "+":
                slave_dev.down()

            exec_cmd('echo "%s%s" > %s/slaves' % (mark, slave_name,
                                                  self._get_bond_dir()))

    def create(self):
        self._add_rm_bond("+")

    def destroy(self):
        self._add_rm_bond("-")

    def configure(self):
        self._setup_options()
        self._add_rm_slaves("+")

    def deconfigure(self):
        self._add_rm_slaves("-")

class NetConfigDeviceBridge(NetConfigDeviceGeneric):
    _modulename = "bridge"

    def _add_rm_bridge(self, prefix):
        exec_cmd("brctl %sbr %s " % (prefix, self._dev_config["name"]))

    def _add_rm_port(self, prefix, slave_id):
        port_name = self._if_manager.get_mapped_device(slave_id).get_name()
        exec_cmd("brctl %sif %s %s" % (prefix, self._dev_config["name"],
                                       port_name))

    def _add_rm_ports(self, prefix):
        for slave_id in get_slaves(self._dev_config):
            self._add_rm_port(prefix, slave_id)

    def create(self):
        self._add_rm_bridge("add")

    def destroy(self):
        self._add_rm_bridge("del")

    def configure(self):
        self._add_rm_ports("add")

    def deconfigure(self):
        self._add_rm_ports("del")

    def slave_add(self, slave_id):
        self._add_rm_port("add", slave_id)

    def slave_del(self, slave_id):
        self._add_rm_port("del", slave_id)

class NetConfigDeviceMacvlan(NetConfigDeviceGeneric):
    _modulename = "macvlan"

    def create(self):
        config = self._dev_config;
        realdev_id = config["slaves"][0]
        realdev_name = self._if_manager.get_mapped_device(realdev_id).get_name()
        dev_name = config["name"]

        hwaddr = ""
        for opt, value in config["options"]:
            if opt == "hwaddr":
                hwaddr = " address %s" % value

        exec_cmd("ip link add link %s %s%s type macvlan"
                                    % (realdev_name, dev_name, hwaddr))

    def destroy(self):
        dev_name = self._dev_config["name"]
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
        config = self._dev_config;
        realdev_id = get_slaves(config)[0]
        realdev_name = self._if_manager.get_mapped_device(realdev_id).get_name()
        dev_name = config["name"]
        vlan_tci = int(get_option(config, "vlan_tci"))
        return dev_name, realdev_name, vlan_tci

    def create(self):
        dev_name, realdev_name, vlan_tci = self._get_vlan_info()
        if self._check_ip_link_add():
            exec_cmd("ip link add link %s %s type vlan id %d"
                                    % (realdev_name, dev_name, vlan_tci))
        else:
            if not re.match(r'^%s.%d$' % (realdev_name, vlan_tci), dev_name):
                logging.error("Since using old vlan manipulation interface, "
                          "devname \"%s\" cannot be used" % dev_name)
                raise Exception("Bad vlan device name")
            exec_cmd("vconfig add %s %d" % (realdev_name, vlan_tci))

    def destroy(self):
        dev_name = self._get_vlan_info()[0]
        if self._check_ip_link_add():
            exec_cmd("ip link del %s" % dev_name)
        else:
            exec_cmd("vconfig rem %s" % dev_name)

    def up(self):
        parent_id = get_slaves(self._dev_config)[0]
        parent_dev = self._if_manager.get_mapped_device(parent_id)
        exec_cmd("ip link set %s up" % parent_dev.get_name())

        super(NetConfigDeviceVlan, self).up()

def prepare_json_str(json_str):
    if not json_str:
        return ""
    json_str = json_str.replace('"', '\\"')
    json_str = re.sub('\s+', ' ', json_str)
    return json_str

class NetConfigDeviceTeam(NetConfigDeviceGeneric):
    _modulename = "team_mode_roundrobin team_mode_activebackup team_mode_broadcast team_mode_loadbalance team"
    _moduleload = False
    _cleanupcmd = "killall -q teamd"

    def _should_enable_dbus(self):
        dbus_disabled = get_option(self._dev_config, "dbus_disabled")
        if not dbus_disabled or bool_it(dbus_disabled):
            return True
        return False

    def _ports_down(self):
        for slave_id in get_slaves(self._dev_config):
            port_dev = self._if_manager.get_mapped_device(slave_id)
            port_dev.down()

    def _ports_up(self):
        for slave_id in get_slaves(self._dev_config):
            port_dev = self._if_manager.get_mapped_device(slave_id)
            port_dev.up()

    def create(self):
        teamd_config = get_option(self._dev_config, "teamd_config")
        teamd_config = prepare_json_str(teamd_config)

        dev_name = self._dev_config["name"]

        dbus_option = " -D" if self._should_enable_dbus() else ""
        exec_cmd("teamd -r -d -c \"%s\" -t %s %s" % (teamd_config, dev_name, dbus_option))

    def destroy(self):
        dev_name = self._dev_config["name"]
        exec_cmd("teamd -k -t %s" % dev_name)

    def configure(self):
        self._ports_down()

        for slave_id in get_slaves(self._dev_config):
            self.slave_add(slave_id)
        self._ports_up()

    def deconfigure(self):
        for slave_id in get_slaves(self._dev_config):
            self.slave_del(slave_id)

    def slave_add(self, slave_id):
        dev_name = self._dev_config["name"]
        port_dev = self._if_manager.get_mapped_device(slave_id)
        port_name = port_dev.get_name()
        teamd_port_config = get_slave_option(self._dev_config,
                                             slave_id,
                                             "teamd_port_config")
        dbus_option = "-D" if self._should_enable_dbus() else ""
        if teamd_port_config:
            teamd_port_config = prepare_json_str(teamd_port_config)
            exec_cmd("teamdctl %s %s port config update %s \"%s\"" % (dbus_option, dev_name, port_name, teamd_port_config))
        port_dev.down()
        exec_cmd("teamdctl %s %s port add %s" % (dbus_option, dev_name, port_name))

    def slave_del(self, slave_id):
        dev_name = self._dev_config["name"]
        port_dev = self._if_manager.get_mapped_device(slave_id)
        port_name = port_dev.get_name()
        dbus_option = "-D" if self._should_enable_dbus() else ""
        exec_cmd("teamdctl %s %s port remove %s" % (dbus_option, dev_name, port_name))

class NetConfigDeviceOvsBridge(NetConfigDeviceGeneric):
    _modulename = "openvswitch"
    _moduleload = True

    @classmethod
    def type_init(self):
        super(NetConfigDeviceOvsBridge, self).type_init()
        exec_cmd("mkdir -p /var/run/openvswitch/")
        exec_cmd("ovsdb-server --detach --pidfile "\
                              "--remote=punix:/var/run/openvswitch/db.sock",
                              die_on_err=False)
        exec_cmd("ovs-vswitchd --detach --pidfile", die_on_err=False)

    def _add_ports(self):
        slaves = self._dev_config["slaves"]
        vlans = self._dev_config["ovs_conf"]["vlans"]

        br_name = self._dev_config["name"]

        bond_ports = []
        for bond in self._dev_config["ovs_conf"]["bonds"].itervalues():
            for slave_id in bond["slaves"]:
                bond_ports.append(slave_id)

        for slave_id in slaves:
            if slave_id in bond_ports:
                continue
            slave_dev = self._if_manager.get_mapped_device(slave_id)
            slave_name = slave_dev.get_name()

            vlan_tags = []
            for tag, vlan in vlans.iteritems():
                if slave_id in vlan["slaves"]:
                    vlan_tags.append(tag)
            if len(vlan_tags) == 0:
                tags = ""
            elif len(vlan_tags) == 1:
                tags = " tag=%s" % vlan_tags[0]
            elif len(vlan_tags) > 1:
                tags = " trunks=" + ",".join(vlan_tags)
            exec_cmd("ovs-vsctl add-port %s %s%s" % (br_name, slave_name, tags))

    def _del_ports(self):
        slaves = self._dev_config["slaves"]

        br_name = self._dev_config["name"]

        bond_ports = []
        for bond in self._dev_config["ovs_conf"]["bonds"].itervalues():
            for slave_id in bond["slaves"]:
                bond_ports.append(slave_id)

        for slave_id in slaves:
            if slave_id in bond_ports:
                continue
            slave_dev = self._if_manager.get_mapped_device(slave_id)
            slave_name = slave_dev.get_name()

            exec_cmd("ovs-vsctl del-port %s %s" % (br_name, slave_name))

    def _add_bonds(self):
        br_name = self._dev_config["name"]

        bonds = self._dev_config["ovs_conf"]["bonds"]
        for bond_id, bond in bonds.iteritems():
            ifaces = ""
            for slave_id in bond["slaves"]:
                slave_dev = self._if_manager.get_mapped_device(slave_id)
                slave_name = slave_dev.get_name()
                ifaces += " %s" % slave_name
            opts = ""
            for option in bond["options"]:
                opts += " %s=%s" % (option["name"], option["value"])
            exec_cmd("ovs-vsctl add-bond %s %s %s %s" % (br_name, bond_id,
                                                         ifaces, opts))

    def _del_bonds(self):
        br_name = self._dev_config["name"]

        bonds = self._dev_config["ovs_conf"]["bonds"]
        for bond_id, bond in bonds.iteritems():
            exec_cmd("ovs-vsctl del-port %s %s" % (br_name, bond_id))

    def create(self):
        dev_cfg = self._dev_config
        br_name = dev_cfg["name"]
        exec_cmd("ovs-vsctl add-br %s" % br_name)

    def destroy(self):
        dev_cfg = self._dev_config
        br_name = dev_cfg["name"]
        exec_cmd("ovs-vsctl del-br %s" % br_name)

    def configure(self):
        self._add_ports()

        self._add_bonds()

    def deconfigure(self):
        self._del_bonds()

        self._del_ports()

class NetConfigDeviceVEth(NetConfigDeviceGeneric):
    _modulename = ""
    _moduleload = False

    def create(self):
        conf = self._dev_config
        exec_cmd("ip link add %s type veth peer name %s" % (conf["name"],
                                                            conf["peer_name"]))

    def destroy(self):
        conf = self._dev_config
        exec_cmd("ip link del %s" % conf["name"])

    def configure(self):
        #no configuration options supported at the moment
        return True

    def deconfigure(self):
        return True

class NetConfigDeviceVti(NetConfigDeviceGeneric):
    _modulename = ""
    _moduleload = False

    def create(self):
        conf = self._dev_config
        local = ''
        remote = ''
        key = None
        for opt, val in conf['options']:
            if opt == 'local':
                local = 'local ' + val
            elif opt == 'remote':
                remote = 'remote ' + val
            elif opt == 'key':
                key = val
            else:
                pass

        if key == None:
            raise Exception("Option 'key' not set for a vti device")

        exec_cmd("ip link add %s type vti %s %s key %s" %
                                    (conf["name"], local, remote, key))

    def destroy(self):
        conf = self._dev_config
        exec_cmd("ip link del %s" % conf["name"])

    def configure(self):
        #no configuration options supported at the moment
        return True

    def deconfigure(self):
        return True

type_class_mapping = {
    "eth": NetConfigDeviceEth,
    "bond": NetConfigDeviceBond,
    "bridge": NetConfigDeviceBridge,
    "macvlan": NetConfigDeviceMacvlan,
    "vlan": NetConfigDeviceVlan,
    "team": NetConfigDeviceTeam,
    "ovs_bridge": NetConfigDeviceOvsBridge,
    "veth": NetConfigDeviceVEth,
    "vti": NetConfigDeviceVti,
    "lo": NetConfigDeviceLoopback
}

def NetConfigDevice(dev_config, if_manager):
    '''
    Class dispatcher
    '''
    if is_nm_managed(dev_config, if_manager):
        return nm_type_class_mapping[dev_config["type"]](dev_config, if_manager)
    else:
        return type_class_mapping[dev_config["type"]](dev_config, if_manager)
