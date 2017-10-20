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
from lnst.Common.ExecCmd import exec_cmd
from lnst.Slave.NetConfigCommon import get_slaves, get_option, get_slave_option
from lnst.Slave.NetConfigCommon import parse_netem, get_slave_options
from lnst.Common.Utils import bool_it
from lnst.Common.Utils import check_process_running
from lnst.Slave.NmConfigDevice import type_class_mapping as nm_type_class_mapping
from lnst.Slave.NmConfigDevice import is_nm_managed


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
        exec_cmd("ip link set %s up" % config["name"])

    def down(self):
        config = self._dev_config
        exec_cmd("ip link set %s down" % config["name"])

    def address_setup(self):
        config = self._dev_config
        if "addresses" in config:
            for address in config["addresses"]:
                exec_cmd("ip addr add %s dev %s" % (address, config["name"]))

    def address_cleanup(self):
        config = self._dev_config
        if "addresses" in config:
            for address in config["addresses"]:
                exec_cmd("ip addr del %s dev %s" % (address, config["name"]),
                         die_on_err=False)

    def set_addresses(self, ips):
        self._dev_config["addresses"] = ips

    @classmethod
    def type_init(self):
        if self._modulename and self._moduleload:
            exec_cmd("modprobe %s %s" % (self._modulename, self._moduleparams))

    @classmethod
    def type_cleanup(self):
        if self._cleanupcmd:
            exec_cmd(self._cleanupcmd, die_on_err=False)

    def enable_lldp(self):
        pass

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
        exec_cmd("ethtool -s %s autoneg on" % config["name"])
        if "netem_cmd" in config:
            exec_cmd(config["netem_cmd"].replace("add", "del"))
        if "lldp" in config:
            self.deconfigure_lldp()

    def enable_lldp(self):
        self._dev_config["lldp"] = True

    def deconfigure_lldp(self):
        config = self._dev_config
        up2tc_def = ','.join(["{}:0".format(x) for x in range(8)])
        tsa_def = ','.join(["{}:strict".format(x) for x in range(8)])
        exec_cmd("lldptool -i %s -V ETS-CFG -T up2tc=%s" % (config["name"],
                                                            up2tc_def))
        exec_cmd("lldptool -i %s -V ETS-CFG -T tsa=%s" % (config["name"],
                                                          tsa_def))
        exec_cmd("lldptool -i %s -V PFC -T enabled=none" % config["name"])
        exec_cmd("lldptool -i %s -L adminStatus=disabled" % config["name"])

class NetConfigDeviceGre(NetConfigDeviceGeneric):
    _modulename = "gre"

    def create(self):
        config = self._dev_config
        dev_name = config["name"]
        params = []

        slaves = get_slaves(config)
        if len(slaves) == 1:
            ul_id = slaves[0]
            ul_name = self._if_manager.get_mapped_device(ul_id).get_name()
            params.append(" dev %s" % ul_name)

        for k in ("ttl", "tos", "key", "ikey", "okey",
                  "local_ip", "remote_ip"):
            v = get_option(config, k)
            if v is not None:
                flag = {"local_ip": "local",
                        "remote_ip": "remote"}.get(k, k)
                params.append(" %s %s" % (flag, v))

        for k in ("seq", "iseq", "oseq",
                  "csum", "icsum", "ocsum"):
            v = get_option(config, k)
            if v is not None and bool_it(v):
                params.append(" " + k)

        exec_cmd("ip tunnel add name %s mode gre%s"
                 % (dev_name, "".join(params)))

    def destroy(self):
        dev_name = self._dev_config["name"]
        exec_cmd("ip link del %s" % dev_name)

class NetConfigDeviceIpIp(NetConfigDeviceGeneric):
    _modulename = "ipip"

    def create(self):
        config = self._dev_config
        dev_name = config["name"]
        params = []

        slaves = get_slaves(config)
        if len(slaves) == 1:
            ul_id = slaves[0]
            ul_name = self._if_manager.get_mapped_device(ul_id).get_name()
            params.append(" dev %s" % ul_name)

        v = get_option(config, "local_ip")
        if v is not None:
            params.append(" local %s" % v)

        v = get_option(config, "remote_ip")
        if v is not None:
            params.append(" remote %s" % v)

        exec_cmd("ip tunnel add name %s mode ipip%s"
                 % (dev_name, "".join(params)))

    def destroy(self):
        dev_name = self._dev_config["name"]
        exec_cmd("ip link del %s" % dev_name)

class NetConfigDeviceLoopback(NetConfigDeviceGeneric):
    def configure(self):
        config = self._dev_config

    def down(self):
        # We do not want to bring loopback device down in root namespace as
        # this might have an unpredictable impact on further testing.
        # In case of non-root namespace leaving loopback device up is not
        # a problem since the namespace will get destroyed after recipe is
        # finished. So, we will remove the configured addresses only
        config = self._dev_config
        if "addresses" in config:
            for address in config["addresses"]:
                exec_cmd("ip addr del %s dev %s" % (address, config["name"]),
                         die_on_err=False)

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

    def _get_bridge_dir(self):
        return "/sys/class/net/%s/bridge" % self._dev_config["name"]

    def _setup_options(self):
        if not "options" in self._dev_config:
            return
        options = self._dev_config["options"]

        for option, value in options:
            exec_cmd('echo "%s" > %s/%s' % (value,
                                            self._get_bridge_dir(),
                                            option))

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
        self._setup_options()
        self._add_rm_ports("add")

    def deconfigure(self):
        self._add_rm_ports("del")

    def slave_add(self, slave_id):
        self._add_rm_port("add", slave_id)
        self._dev_config["slaves"].append(slave_id)

    def slave_del(self, slave_id):
        self._dev_config["slaves"].remove(slave_id)
        self._add_rm_port("del", slave_id)

class NetConfigDeviceDummy(NetConfigDeviceGeneric):
    _modulename = ""

    def create(self):
        dev_name = self._dev_config["name"]
        exec_cmd("ip link add %s type dummy" % dev_name)

    def destroy(self):
        dev_name = self._dev_config["name"]
        exec_cmd("ip link del %s" % dev_name)

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
        parent_dev.link_up()

        super(NetConfigDeviceVlan, self).up()

class NetConfigDeviceVxlan(NetConfigDeviceGeneric):
    _modulename = ""

    def create(self):
        config = self._dev_config

        slaves = get_slaves(config)
        if len(slaves) == 1:
            realdev_id = slaves[0]
            name = self._if_manager.get_mapped_device(realdev_id).get_name()
            dev_param = "dev %s" % name
        else:
            dev_param = ""

        dev_name = config["name"]
        vxlan_id = int(get_option(config, "id"))
        group_ip = get_option(config, "group_ip")
        remote_ip = get_option(config, "remote_ip")
        extra = get_option(config, "extra") or ''

        if group_ip:
            group_or_remote = "group %s" % group_ip
        elif remote_ip:
            group_or_remote = "remote %s" % remote_ip
        else:
            raise Exception("group or remote must be specified for vxlan")

        dstport = get_option(config, "dstport")
        if not dstport:
            dstport = 0
        else:
            dstport = int(dstport)

        exec_cmd("ip link add %s type vxlan id %d %s %s dstport %d %s"
                                % (dev_name,
                                   vxlan_id,
                                   dev_param,
                                   group_or_remote,
                                   dstport,
                                   extra))

    def destroy(self):
        dev_name = self._dev_config["name"]
        exec_cmd("ip link del %s" % dev_name)

    def up(self):
        slaves = get_slaves(self._dev_config)
        if len(slaves) == 1:
            parent_id = get_slaves(self._dev_config)[0]
            parent_dev = self._if_manager.get_mapped_device(parent_id)
            parent_dev.link_up()

        super(NetConfigDeviceVxlan, self).up()

def prepare_json_str(json_str):
    if not json_str:
        return "{}"
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
            self._slave_add(slave_id)
        self._ports_up()

    def deconfigure(self):
        for slave_id in get_slaves(self._dev_config):
            self._slave_del(slave_id)

    def _slave_add(self, slave_id):
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

    def slave_add(self, slave_id):
        self._slave_add(slave_id)
        self._dev_config["slaves"].append(slave_id)

    def _slave_del(self, slave_id):
        dev_name = self._dev_config["name"]
        port_dev = self._if_manager.get_mapped_device(slave_id)
        port_name = port_dev.get_name()
        dbus_option = "-D" if self._should_enable_dbus() else ""
        exec_cmd("teamdctl %s %s port remove %s" % (dbus_option, dev_name, port_name))

    def slave_del(self, slave_id):
        self._dev_config["slaves"].remove(slave_id)
        self._slave_del(slave_id)

class NetConfigDeviceOvsBridge(NetConfigDeviceGeneric):
    _modulename = "openvswitch"
    _moduleload = True

    def up(self):
        super(NetConfigDeviceOvsBridge, self).up()

        int_ports = self._dev_config["ovs_conf"]["internals"]
        br_name = self._dev_config["name"]
        for iport in int_ports:
            exec_cmd("ip link set %s up" % iport["name"])

    def down(self):
        int_ports = self._dev_config["ovs_conf"]["internals"]
        br_name = self._dev_config["name"]
        for iport in int_ports:
            exec_cmd("ip link set %s down" % iport["name"])

        super(NetConfigDeviceOvsBridge, self).down()

    def address_setup(self):
        super(NetConfigDeviceOvsBridge, self).up()
        super(NetConfigDeviceOvsBridge, self).address_setup()

        int_ports = self._dev_config["ovs_conf"]["internals"]
        br_name = self._dev_config["name"]
        for iport in int_ports:
            if "addresses" in iport:
                for address in iport["addresses"]:
                    exec_cmd("ip addr add %s dev %s" % (address, iport["name"]))

    def address_cleanup(self):
        super(NetConfigDeviceOvsBridge, self).down()
        super(NetConfigDeviceOvsBridge, self).address_cleanup()

        int_ports = self._dev_config["ovs_conf"]["internals"]
        br_name = self._dev_config["name"]
        for iport in int_ports:
            if "addresses" in iport:
                for address in iport["addresses"]:
                    exec_cmd("ip addr del %s dev %s" % (address, iport["name"]),
                             die_on_err=False)

    @classmethod
    def type_init(self):
        super(NetConfigDeviceOvsBridge, self).type_init()
        if not check_process_running("ovsdb-server"):
            exec_cmd("mkdir -p /var/run/openvswitch/")
            exec_cmd("ovsdb-server --detach --pidfile "\
                              "--remote=punix:/var/run/openvswitch/db.sock",
                              die_on_err=False)
        if not check_process_running("ovs-vswitchd"):
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

            options = ""
            for opt in get_slave_options(self._dev_config, slave_id):
                options += " %s=%s" % (opt[0], opt[1])

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

            if options != "":
                exec_cmd("ovs-vsctl set Interface %s%s" % (slave_name, options))

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

    def _add_internal_ports(self):
        int_ports = self._dev_config["ovs_conf"]["internals"]
        br_name = self._dev_config["name"]

        for i in int_ports:
            i["name"] = self._if_manager.assign_name_generic(prefix="int")

            options = ""
            if "options" in i:
                for opt in i["options"]:
                    options += " %s=%s" % (opt["name"], opt["value"])

                    if opt["name"] == "name":
                        i["name"] = opt["value"]

            exec_cmd("ovs-vsctl add-port %s %s -- set Interface %s "\
                     "type=internal %s" % (br_name, i["name"],
                                           i["name"], options))

    def _del_internal_ports(self):
        int_ports = self._dev_config["ovs_conf"]["internals"]
        br_name = self._dev_config["name"]

        for i in int_ports:
            exec_cmd("ovs-vsctl del-port %s %s" % (br_name, i["name"]))

    def _add_tunnels(self):
        tunnels = self._dev_config["ovs_conf"]["tunnels"]
        br_name = self._dev_config["name"]

        for i in tunnels:
            i["name"] = self._if_manager.assign_name_generic(prefix=i["type"])

            options = ""
            for opt in i["options"]:
                options += " %s=%s" % (opt["name"], opt["value"])

                if opt["name"] == "name":
                    i["name"] = opt["value"]

            exec_cmd("ovs-vsctl add-port %s %s -- set Interface %s "\
                     "type=%s %s" % (br_name, i["name"], i["name"],
                                     i["type"], options))

    def _del_tunnels(self):
        tunnels = self._dev_config["ovs_conf"]["tunnels"]
        br_name = self._dev_config["name"]

        for i in tunnels:
            exec_cmd("ovs-vsctl del-port %s %s" % (br_name, i["name"]))

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

    def _add_flow_entries(self):
        br_name = self._dev_config["name"]
        entries = self._dev_config["ovs_conf"]["flow_entries"]

        for entry in entries:
            exec_cmd("ovs-ofctl add-flow %s '%s'" % (br_name, entry))

    def _del_flow_entries(self):
        br_name = self._dev_config["name"]
        exec_cmd("ovs-ofctl del-flows %s" % (br_name))

    def create(self):
        dev_cfg = self._dev_config
        br_name = dev_cfg["name"]
        exec_cmd("ovs-vsctl add-br %s" % br_name)

        self._add_internal_ports()
        self._add_tunnels()

    def destroy(self):
        self._del_tunnels()
        self._del_internal_ports()

        dev_cfg = self._dev_config
        br_name = dev_cfg["name"]
        exec_cmd("ovs-vsctl del-br %s" % br_name)

    def configure(self):
        self._add_ports()
        self._add_bonds()
        self._add_flow_entries()

    def deconfigure(self):
        self._del_flow_entries()
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

class NetConfigDeviceVti6(NetConfigDeviceGeneric):
    _modulename = ""
    _moduleload = False

    def create(self):
        conf = self._dev_config
        local = ''
        remote = ''
        key = None
        device = ''
        for opt, val in conf['options']:
            if opt == 'local':
                local = 'local ' + val
            elif opt == 'remote':
                remote = 'remote ' + val
            elif opt == 'key':
                key = val
            elif opt == 'dev':
                device = 'dev ' + val
            else:
                pass

        if key == None:
            raise Exception("Option 'key' not set for a vti6 device")

        exec_cmd("ip link add %s type vti6 %s %s key %s %s" %
                                    (conf["name"], local, remote, key, device))

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
    "vti6": NetConfigDeviceVti6,
    "lo": NetConfigDeviceLoopback,
    "vxlan": NetConfigDeviceVxlan,
    "dummy": NetConfigDeviceDummy,
    "gre": NetConfigDeviceGre,
    "ipip": NetConfigDeviceIpIp,
}

def NetConfigDevice(dev_config, if_manager):
    '''
    Class dispatcher
    '''
    if is_nm_managed(dev_config, if_manager):
        return nm_type_class_mapping[dev_config["type"]](dev_config, if_manager)
    else:
        return type_class_mapping[dev_config["type"]](dev_config, if_manager)
