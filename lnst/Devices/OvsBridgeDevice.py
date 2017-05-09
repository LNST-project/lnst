"""
Defines the OvsBridgeDevice class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Common.ExecCmd import exec_cmd
from lnst.Devices.Device import Device, DeviceError
from lnst.Devices.SoftDevice import SoftDevice

class OvsBridgeDevice(SoftDevice):
    _name_template = "t_ovsbr"

    _modulename = "openvswitch"

    @classmethod
    def _type_init(cls):
        if not cls._type_initialized:
            super(OvsBridgeDevice, cls)._type_init()

            exec_cmd("mkdir -p /var/run/openvswitch/")
            exec_cmd("ovsdb-server --detach --pidfile "\
                     "--remote=punix:/var/run/openvswitch/db.sock",
                     die_on_err=False)
            exec_cmd("ovs-vswitchd --detach --pidfile", die_on_err=False)

            cls._type_initialized = True

    def create(self):
        exec_cmd("ovs-vsctl add-br %s" % self.name)

    def destroy(self):
        exec_cmd("ovs-vsctl del-br %s" % self.name)

    def port_add(self, dev, **kwargs):
        options = ""
        for opt_name, opt_value in kwargs.items():
            options += " %s=%s" % (opt_name, opt_value)

        exec_cmd("ovs-vsctl add-port %s %s%s" % (self.name, dev.name, options))

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

    def internal_port_add(self, **kwargs):
        name = self._if_manager.assign_name("int")

        options = ""
        for opt_name, opt_value in kwargs.items():
            if opt_name == "name":
                name = opt_value
                continue

            options += " %s=%s" % (opt_name, opt_value)

        exec_cmd("ovs-vsctl add-port %s %s -- set Interface %s "\
                 "type=internal %s" % (self.name, name,
                                       name, options))

        dev = self._if_manager.get_device_by_name(name)
        return dev

    def tunnel_add(self, tunnel_type, options):
        name = self._if_manager.assign_name(tunnel_type)

        options = ""
        for opt_name, opt_value in options.items():
            if opt_name == "name":
                name = opt_value
                continue

            options += " %s=%s" % (opt_name, opt_value)

        exec_cmd("ovs-vsctl add-port %s %s -- set Interface %s "\
                 "type=%s %s" % (self.name, name, name,
                                 tunnel_type, options))

    def tunnel_del(self, name):
        self.port_del(name)

    def flow_add(self, entry):
        exec_cmd("ovs-ofctl add-flow %s '%s'" % (self.name, entry))

    def flows_add(self, entries):
        for entry in entries:
            self.flow_add(entry)

    def flows_del(self, entry):
        exec_cmd("ovs-ofctl del-flows %s" % (self.name))
