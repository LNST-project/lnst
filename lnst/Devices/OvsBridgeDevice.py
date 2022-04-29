"""
Defines the OvsBridgeDevice class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import re
import pprint
from lnst.Common.ExecCmd import exec_cmd
from lnst.Common.DeviceError import DeviceError
from lnst.Devices.Device import Device
from lnst.Devices.SoftDevice import SoftDevice

class OvsBridgeDevice(SoftDevice):
    _name_template = "t_ovsbr"

    def __init__(self, ifmanager, *args, **kwargs):
        super(OvsBridgeDevice, self).__init__(ifmanager)
        self._type_init()

    @classmethod
    def _type_init(cls):
        exec_cmd("systemctl start openvswitch.service", die_on_err=False)

    def _create(self):
        exec_cmd("ovs-vsctl add-br %s" % self.name)

    def destroy(self):
        exec_cmd("ovs-vsctl del-br %s" % self.name)

    def _dict_to_keyvalues(self, options):
        opts = ""
        for opt_name, opt_value in options.items():
            opts += " %s=%s" % (opt_name, opt_value)

        return opts

    def _interface_cmd(self, interface, options):
        keyvalues = self._dict_to_keyvalues(options)
        cmd = ""
        if len(keyvalues):
            cmd = " -- set Interface {} {}".format(interface, keyvalues)

        return cmd

    def _format_ovs_json_value(self, value):
        formatted_value = None
        if type(value) == list:
            value_type = value[0]

            if value_type == 'map':
                formatted_value = value[1]
            elif value_type == 'set':
                formatted_value = value[1]
            elif value_type == 'uuid':
                formatted_value = value[1]
            else:
                raise Exception("Unknown type in ovs json output: {}".format(
                    value_type))
        else:
            formatted_value = value

        return formatted_value

    def _format_ovs_json(self, ovs_json):
        headings = ovs_json['headings']
        data = ovs_json['data']

        formatted_data = []

        for data_entry in data:
            formatted_fields = {}
            for i, entry_value in enumerate(data_entry):
                formatted_fields[headings[i]] = self._format_ovs_json_value(entry_value)
            formatted_data.append(formatted_fields)

        return formatted_data

    def _list_ports(self):
        out_json = exec_cmd("ovs-vsctl --format json list port",
                log_outputs=False, json=True)[0]

        return self._format_ovs_json(out_json)

    def _list_interfaces(self):
        out_json = exec_cmd("ovs-vsctl --format json list interface",
                log_outputs=False, json=True)[0]

        return self._format_ovs_json(out_json)

    def port_add(self, device=None, port_options={}, interface_options={}):
        if device is None:
            dev_name = interface_options.get('name',
                self._if_manager.assign_name(interface_options['type']))
        else:
            dev_name = device.name

        exec_cmd("ovs-vsctl add-port {} {}{}{}".format(self.name, dev_name,
            self._dict_to_keyvalues(port_options),
            self._interface_cmd(dev_name, interface_options)))

        iface = None
        if 'type' in interface_options and interface_options['type'] == 'internal':
            iface = self._if_manager.get_device_by_name(dev_name)
            iface._enable()

        return iface

    def port_del(self, dev):
        if isinstance(dev, Device):
            exec_cmd("ovs-vsctl del-port %s %s" % (self.name, dev.name))
        elif isinstance(dev, str):
            exec_cmd("ovs-vsctl del-port %s %s" % (self.name, dev))
        else:
            raise DeviceError("Invalid port_del argument %s" % str(dev))

    def bond_add(self, port_name, devices, **kwargs):
        dev_names = ""
        for dev in devices:
            dev_names += " %s" % dev.name

        options = ""
        for opt_name, opt_value in kwargs.items():
            options += " %s=%s" % (opt_name, opt_value)

        exec_cmd("ovs-vsctl add-bond %s %s %s %s" % (self.name, port_name,
                                                     dev_names, options))

    def bond_del(self, dev):
        self.port_del(dev)

    def tunnel_add(self, tunnel_type, options):
        options_copy = options.copy()
        options_copy['type'] = tunnel_type
        self.port_add(device=None, interface_options=options_copy)

    def tunnel_del(self, name):
        self.port_del(name)

    def flow_add(self, entry):
        exec_cmd("ovs-ofctl add-flow %s '%s'" % (self.name, entry))

    def flows_add(self, entries):
        for entry in entries:
            self.flow_add(entry)

    def flows_del(self, entry):
        exec_cmd("ovs-ofctl del-flows %s" % (self.name))

    @property
    def ports(self):
        ports = self._list_ports()
        interfaces = self._list_interfaces()

        filtered_ports = {}

        for port in ports:
            port_iface_uuid = port['interfaces']
            port_ifaces = [ iface for iface in interfaces if iface['_uuid'] == port_iface_uuid ]
            if len(port_ifaces):
                port_iface = port_ifaces[0]
                filtered_ports[port['name']] = {
                        'interface': port_iface['name'],
                        'type': port_iface['type'],
                        'options': port_iface['options'],
                        }

        return filtered_ports

    @property
    def tunnels(self):
        tunnels = self.ports.copy()

        for port in self.ports.keys():
            if tunnels[port]['type'] in ['', 'internal']:
                del tunnels[port]

        return tunnels

    @property
    def bonds(self):
        bonds = {}
        bond_list = []
        out = exec_cmd("ovs-appctl bond/list", log_outputs=False)[0]

        for line in out.split('\n'):
            if line:
                bond_list.append(line.split('\t'))

        for bond in bond_list[1:]:
            bonds[bond[0]] = {'type' : bond[1], 'slaves' : bond[3]}

        return bonds

    @property
    def flows_str(self):
        flows = []
        ignore_exprs = [r"cookie", r"duration", r"n_packets",
            r"n_bytes", r"idle_age"]
        out = exec_cmd("ovs-ofctl dump-flows %s" % self.name,
            log_outputs=False)[0]

        for line in out.split('\n'):
            if line:
                flows.append(line.split(', '))

        for flow in flows[1:]:
            for entry in list(flow):
                for expr in ignore_exprs:
                    if re.search(expr, entry):
                        del flow[flow.index(entry)]
                        break

        return pprint.pformat(flows[1:])
