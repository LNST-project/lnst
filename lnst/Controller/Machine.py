"""
This file containst classes for representing and handling
a Machine and an Interface in LNST

Copyright 2013 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import logging
import socket
import os
import re
import pickle
import tempfile
import signal
from time import sleep
from xmlrpclib import Binary
from pprint import pprint, pformat
from lnst.Common.Config import lnst_config
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.NetUtils import MacPool, normalize_hwaddr
from lnst.Common.Utils import wait_for, md5sum, dir_md5sum, create_tar_archive
from lnst.Common.Utils import check_process_running
from lnst.Common.ConnectionHandler import send_data, recv_data
from lnst.Common.ConnectionHandler import ConnectionHandler

# conditional support for libvirt
if check_process_running("libvirtd"):
    from lnst.Controller.VirtUtils import VirtNetCtl, VirtDomainCtl

DEFAULT_TIMEOUT = 60

class MachineError(Exception):
    pass

class PrefixMissingError(Exception):
    pass

class Machine(object):
    """ Slave machine abstraction

        A machine object represents a handle using which the controller can
        manipulate the machine. This includes tasks such as, configuration,
        deconfiguration, and running commands.
    """

    def __init__(self, m_id, hostname=None, libvirt_domain=None, rpcport=None):
        self._id = m_id
        self._hostname = hostname
        self._connection = None
        self._configured = False
        self._system_config = {}

        self._domain_ctl = None
        self._network_bridges = None
        self._libvirt_domain = libvirt_domain
        if libvirt_domain:
            self._domain_ctl = VirtDomainCtl(libvirt_domain)

        if rpcport:
            self._port = rpcport
        else:
            self._port = lnst_config.get_option('environment', 'rpcport')

        self._msg_dispatcher = None
        self._mac_pool = None

        self._interfaces = []

    def _add_interface(self, if_id, if_type, cls):
        if if_id != None:
            for iface in self._interfaces:
                if if_id == iface.get_id():
                    msg = "Interface '%s' already exists on machine '%s'" \
                                                 % (if_id, self._id)
                    raise MachineError(msg)

        iface = cls(self, if_id, if_type)
        self._interfaces.append(iface)
        return iface

    def interface_update(self, if_data):
        try:
            iface = self.get_interface(if_data["if_id"])
        except:
            iface = None
        if iface:
            iface.set_hwaddr(if_data["hwaddr"])
            iface.set_devname(if_data["devname"])

    #
    # Factory methods for constructing interfaces on this machine. The
    # types of interfaces are explained with the classes below.
    #
    def new_static_interface(self, if_id, if_type):
        return self._add_interface(if_id, if_type, StaticInterface)

    def new_unused_interface(self, if_type):
        return self._add_interface(None, if_type, UnusedInterface)

    def new_virtual_interface(self, if_id, if_type):
        return self._add_interface(if_id, if_type, VirtualInterface)

    def new_soft_interface(self, if_id, if_type):
        return self._add_interface(if_id, if_type, SoftInterface)

    def get_interface(self, if_id):
        for iface in self._interfaces:
            if iface.get_id != None and if_id == iface.get_id():
                return iface

        msg = "Interface '%s' not found on machine '%s'" % (if_id, self._id)
        raise MachineError(msg)

    def get_ordered_interfaces(self):
        ordered_list = list(self._interfaces)
        change = True
        while change:
            change = False
            swap = False
            ind1 = 0
            ind2 = 0
            for i in ordered_list:
                master = i.get_primary_master()
                if master != None:
                    ind1 = ordered_list.index(i)
                    ind2 = ordered_list.index(master)
                    if ind1 > ind2:
                        swap = True
                        break
            if swap:
                change = True
                tmp = ordered_list[ind1]
                ordered_list[ind1] = ordered_list[ind2]
                ordered_list[ind2] = tmp
        return ordered_list

    def _rpc_call(self, method_name, *args):
        data = {"type": "command", "method_name": method_name, "args": args}

        self._msg_dispatcher.send_message(self._id, data)
        result = self._msg_dispatcher.wait_for_result(self._id)

        return result

    def configure(self, recipe_name):
        """ Prepare the machine

            Calling this method will initialize the rpc connection to the
            machine and initialize all the interfaces. Note, that it will
            *not* configure the interfaces. They need to be configured
            individually later on.
        """
        hostname = self._hostname
        port = self._port
        m_id = self._id

        logging.info("Connecting to RPC on machine %s (%s)", m_id, hostname)
        connection = socket.create_connection((hostname, port))
        self._msg_dispatcher.add_slave(self, connection)

        hello = self._rpc_call("hello", recipe_name)
        if hello != "hello":
            msg = "Unable to establish RPC connection " \
                  "to machine %s, handshake failed!" % hostname
            raise Machine(msg)

        for iface in self._interfaces:
            iface.initialize()

        self._configured = True

    def is_configured(self):
        """ Test if the machine was configured """

        return self._configured

    def cleanup(self, deconfigure=True):
        """ Clean the machine up

            This is the counterpart of the configure() method. It will
            stop any still active commands on the machine, deconfigure
            all the interfaces that have been configured on the machine,
            and finalize and close the rpc connection to the machine.
        """
        if not self._configured:
            return

        #connection to the slave was closed
        if not self._msg_dispatcher.get_connection(self._id):
            return

        ordered_ifaces = self.get_ordered_interfaces()
        try:
            self._rpc_call("kill_cmds")

            if deconfigure:
                ordered_ifaces.reverse()
                for iface in ordered_ifaces:
                    iface.deconfigure()
                for iface in ordered_ifaces:
                    iface.cleanup()

            self._rpc_call("bye")
        except:
            #cleanup is only meaningful on dynamic interfaces, and should
            #always be called when deconfiguration happens- especially
            #when something on the slave breaks during deconfiguration
            for iface in ordered_ifaces:
                if not isinstance(iface, VirtualInterface):
                    continue
                iface.cleanup()
            raise
        finally:
            self._msg_dispatcher.disconnect_slave(self.get_id())

            self._configured = False

    def _timeout_handler(self, signum, frame):
        msg = "RPC connection to machine %s timed out" % self.get_id()
        raise MachineError(msg)

    def run_command(self, command):
        """ Run a command on the machine """

        prev_handler = signal.signal(signal.SIGALRM, self._timeout_handler)

        if "timeout" in command:
            timeout = command["timeout"]
            logging.debug("Setting timeout to \"%d\"", timeout)
            signal.alarm(timeout)
        else:
            logging.debug("Setting default timeout (%ds)." % DEFAULT_TIMEOUT)
            signal.alarm(DEFAULT_TIMEOUT)

        try:
            cmd_res = self._rpc_call("run_command", command)
        except MachineError as exc:
            if "bg_id" in command:
                cmd_res = self._rpc_call("kill_command", command["bg_id"])
            else:
                cmd_res = self._rpc_call("kill_command", None)
            cmd_res["passed"] = False
            cmd_res["msg"] = str(exc)

        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev_handler)

        return cmd_res

    def get_hostname(self):
        """ Get hostname/ip of the machine

            This will return the hostname/ip of the machine's controller
            interface.
        """
        return self._hostname

    def get_libvirt_domain(self):
        return self._libvirt_domain

    def get_id(self):
        """ Returns machine's id as defined in the recipe """
        return self._id

    def set_rpc(self, dispatcher):
        self._msg_dispatcher = dispatcher

    def get_mac_pool(self):
        if self._mac_pool:
            return self._mac_pool
        else:
            raise MachineError("Mac pool not available.")

    def set_mac_pool(self, mac_pool):
        self._mac_pool = mac_pool

    def restore_system_config(self):
        return self._rpc_call("restore_system_config")

    def set_network_bridges(self, bridges):
        self._network_bridges = bridges

    def get_network_bridges(self):
        if self._network_bridges != None:
            return self._network_bridges
        else:
            raise MachineError("Network bridges not available.")

    def get_domain_ctl(self):
        if not self._domain_ctl:
            raise MachineError("Machine '%s' is not virtual." % self.get_id())

        return self._domain_ctl

    def start_packet_capture(self):
        return self._rpc_call("start_packet_capture", "")

    def stop_packet_capture(self):
        self._rpc_call("stop_packet_capture")

    def copy_file_to_machine(self, local_path, remote_path=None):
        remote_path = self._rpc_call("start_copy_to", remote_path)
        f = open(local_path, "rb")

        while True:
            data = f.read(1024*1024) # 1MB buffer
            if len(data) == 0:
                break

            self._rpc_call("copy_part_to", remote_path, Binary(data))

        self._rpc_call("finish_copy_to", remote_path)
        return remote_path

    def copy_file_from_machine(self, remote_path, local_path):
        status = self._rpc_call("start_copy_from", remote_path)
        if not status:
            raise MachineError("The requested file cannot be transfered." \
                       "It does not exist on machine %s" % self.get_id())

        local_file = open(local_path, "wb")

        buf_size = 1024*1024 # 1MB buffer
        binary = "next"
        while binary != "":
            binary = self._rpc_call("copy_part_from", remote_path, buf_size)
            local_file.write(binary.data)

        local_file.close()
        self._rpc_call("finish_copy_from", remote_path)

    def sync_resources(self, required):
        self._rpc_call("clear_resource_table")

        for res_type, resources in required.iteritems():
            for res_name, res in resources.iteritems():
                has_resource = self._rpc_call("has_resource", res["hash"])
                if not has_resource:
                    msg = "Transfering %s %s to machine %s" % \
                            (res_name, res_type, self.get_id())
                    logging.info(msg)

                    local_path = required[res_type][res_name]["path"]

                    if res_type == "tools":
                        archive = tempfile.NamedTemporaryFile(delete=False)
                        archive_path = archive.name
                        archive.close()

                        create_tar_archive(local_path, archive_path, True)
                        local_path = archive_path

                    remote_path = self.copy_file_to_machine(local_path)
                    self._rpc_call("add_resource_to_cache", res["hash"],
                                  remote_path, res_name, res["path"], res_type)

                    if res_type == "tools":
                        os.unlink(archive_path)

                self._rpc_call("map_resource", res["hash"], res_type, res_name)

    def enable_nm(self):
        return self._rpc_call("enable_nm")

    def disable_nm(self):
        return self._rpc_call("disable_nm")

    def restore_nm_option(self):
        return self._rpc_call("restore_nm_option")

    def __str__(self):
        return "[Machine hostname(%s) libvirt_domain(%s) interfaces(%d)]" % \
               (self._hostname, self._libvirt_domain, len(self._interfaces))

class Interface(object):
    """ Abstraction of a test network interface on a slave machine

        This is a base class for object that represent test interfaces
        on a test machine.
    """
    def __init__(self, machine, if_id, if_type):
        self._machine = machine
        self._configured = False

        self._id = if_id
        self._type = if_type

        self._hwaddr = None
        self._devname = None
        self._network = None

        self._slaves = {}
        self._slave_options = {}
        self._addresses = []
        self._options = []

        self._master = {"primary": None, "other": []}

        self._ovs_conf = None

    def get_id(self):
        return self._id

    def set_hwaddr(self, hwaddr):
        self._hwaddr = normalize_hwaddr(hwaddr)

    def get_hwaddr(self):
        if not self._hwaddr:
            msg = "Hardware address is not available for interface '%s'" \
                  % self.get_id()
            raise MachineError(msg)
        return self._hwaddr

    def set_devname(self, devname):
        self._devname = devname

    def get_devname(self):
        if not self._devname:
            msg = "Device name is not available for interface '%s'" \
                  % self.get_id()
            raise MachineError(msg)
        return self._devname

    def set_network(self, network):
        self._network = network

    def get_network(self):
        if not self._network:
            msg = "Network segment is not available for interface '%s'" \
                  % self.get_id()
            raise MachineError(msg)
        return self._network

    def set_option(self, name, value):
        self._options.append((name, value))

    def add_master(self, master, primary=True):
        if primary and self._master["primary"] != None:
            msg = "Interface %s already has a primary master."\
                    % self._master.get_id()
            raise MachineError(msg)
        else:
            if primary:
                self._master["primary"] = master
            else:
                self._master["other"].append(master)

    def get_primary_master(self):
        return self._master["primary"]

    def add_slave(self, iface):
        self._slaves[iface.get_id()] = iface
        if self._type in ["vlan"]:
            iface.add_master(self, primary=False)
        else:
            iface.add_master(self)

    def set_slave_option(self, slave_id, name, value):
        if slave_id not in self._slave_options:
            self._slave_options[slave_id] = []
        self._slave_options[slave_id].append((name, value))

    def add_address(self, addr):
        self._addresses.append(addr)

    def get_address(self, num):
        return self._addresses[num].split('/')[0]

    def set_ovs_conf(self, ovs_conf):
        self._ovs_conf = ovs_conf

    def get_ovs_conf(self):
        return self._ovs_conf

    def get_prefix(self, num):
        try:
            return self._addresses[num].split('/')[1]
        except IndexError:
            raise PrefixMissingError

    def _get_config(self):
        config = {"hwaddr": self._hwaddr, "type": self._type,
                  "addresses": self._addresses, "slaves": self._slaves.keys(),
                  "options": self._options,
                  "slave_options": self._slave_options,
                  "master": None, "other_masters": [],
                  "ovs_conf": self._ovs_conf}

        if self._master["primary"] != None:
            config["master"] = self._master["primary"].get_id()

        for m in self._master["other"]:
            config["other_masters"].append(m.get_id())

        return config

    def up(self):
        self._machine._rpc_call("set_device_up", self._id)

    def down(self):
        self._machine._rpc_call("set_device_down", self._id)

    def initialize(self):
        phys_devs = self._machine._rpc_call("map_if_by_hwaddr",
                                            self._id, self._hwaddr)

        if len(phys_devs) == 1:
            self.set_devname(phys_devs[0]["name"])
        elif len(phys_devs) < 1:
            msg = "Device %s not found on machine %s" \
                  % (self.get_id(), self._machine.get_id())
            raise MachineError(msg)
        elif len(phys_devs) > 1:
            msg = "More than one device with hwaddr %s found on machine %s" \
                  % (self._hwaddr, self._machine.get_id())
            raise MachineError(msg)

        self.down()

    def cleanup(self):
        pass

    def configure(self):
        if self._configured:
            msg = "Unable to configure interface %s on machine %s. " \
                  "It has been configured already." % (self.get_id(),
                  self._machine.get_id())
            raise MachineError(msg)

        logging.info("Configuring interface %s on machine %s", self.get_id(),
                     self._machine.get_id())

        self._machine._rpc_call("configure_interface", self.get_id(),
                               self._get_config())
        self._configured = True

    def deconfigure(self):
        if not self._configured:
            return

        self._machine._rpc_call("deconfigure_interface", self.get_id())
        self._configured = False

class StaticInterface(Interface):
    """ Static interface

        This class represents interfaces that are present on the
        machine. LNST will only use them for testing without performing
        any special actions.

        This type is suitable for physical interfaces.
    """
    def __init__(self, machine, if_id, if_type):
        super(StaticInterface, self).__init__(machine, if_id, if_type)

class VirtualInterface(Interface):
    """ Dynamically created interface

        This class represents interfaces in libvirt virtual machines
        that were created dynamically by LNST just for this test.

        This requires some special handling and communication with
        libvirt.
    """
    def __init__(self, machine, if_id, if_type):
        super(VirtualInterface, self).__init__(machine, if_id, if_type)
        self._driver = "rtl8139"

    def set_driver(self, driver):
        self._driver = driver

    def get_driver(self):
        return self._driver

    def get_orig_hwaddr(self):
        if not self._orig_hwaddr:
            msg = "Hardware address is not available for interface '%s'" \
                  % self.get_id()
            raise MachineError(msg)
        return self._orig_hwaddr

    def initialize(self):
        domain_ctl = self._machine.get_domain_ctl()

        if self._hwaddr:
            query = self._machine._rpc_call('get_devices_by_hwaddr',
                                           self._hwaddr)
            if len(query):
                msg = "Device with hwaddr %s already exists" % self._hwaddr
                raise MachineError(msg)
        else:
            mac_pool = self._machine.get_mac_pool()
            while True:
                self._hwaddr = normalize_hwaddr(mac_pool.get_addr())
                query = self._machine._rpc_call('get_devices_by_hwaddr',
                                               self._hwaddr)
                if not len(query):
                    break

        bridges = self._machine.get_network_bridges()
        if self._network in bridges:
            net_ctl = bridges[self._network]
        else:
            bridges[self._network] = net_ctl = VirtNetCtl()
            net_ctl.init()

        net_name = net_ctl.get_name()

        logging.info("Creating interface %s (%s) on machine %s",
                     self.get_id(), self._hwaddr, self._machine.get_id())

        self._orig_hwaddr = self._hwaddr
        domain_ctl.attach_interface(self._hwaddr, net_name, self._driver)


        # The sleep here is necessary, because udev sometimes renames the
        # newly created device and if the query for name comes too early,
        # the controller will then try to configure an nonexistent device
        sleep(1)

        ready = wait_for(self.is_ready, timeout=10)

        if not ready:
            msg = "Netdevice initialization failed." \
                  "Unable to create device %s (%s) on machine %s" \
                  % (self.get_id(), self._hwaddr, self._machine.get_id())
            raise MachineError(msg)

        super(VirtualInterface, self).initialize()

    def cleanup(self):
        domain_ctl = self._machine.get_domain_ctl()
        domain_ctl.detach_interface(self._orig_hwaddr)

    def is_ready(self):
        ifaces = self._machine._rpc_call('get_devices_by_hwaddr', self._hwaddr)
        return len(ifaces) > 0

class SoftInterface(Interface):
    """ Software interface abstraction

        This type of interface represents interfaces created in the kernel
        during the runtime. This includes devices such as bonds and teams.
    """

    def __init__(self, machine, if_id, if_type):
        super(SoftInterface, self).__init__(machine, if_id, if_type)

    def initialize(self):
        pass

    def configure(self):
        if self._configured:
            msg = "Unable to configure interface %s on machine %s. " \
                  "It has been configured already." % (self.get_id(),
                  self._machine.get_id())
            raise MachineError(msg)

        logging.info("Configuring interface %s on machine %s", self.get_id(),
                     self._machine.get_id())

        dev_name = self._machine._rpc_call("create_soft_interface", self._id,
                                           self._get_config())
        self.set_devname(dev_name)
        self._configured = True


class UnusedInterface(Interface):
    """ Unused interface for this test

        This class represents interfaces that will not be used in the
        current test setup. This applies when a slave machine from a
        pool has more interfaces then the machine it was matched to
        from the recipe.

        LNST still needs to know about these interfaces so it can turn
        them off.
    """

    def __init__(self, machine, if_id, if_type):
        super(UnusedInterface, self).__init__(machine, if_id, if_type)

    def initialize(self):
        self._machine._rpc_call('set_unmapped_device_down', self._hwaddr)

    def configure(self):
        pass

    def deconfigure(self):
        pass

    def up(self):
        pass

    def down(self):
        pass
