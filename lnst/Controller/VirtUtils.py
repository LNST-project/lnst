"""
Utilities for manipulating virtualization host, its guests and
connections between them

Copyright 2012 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import logging
import libvirt
from libvirt import libvirtError
from lnst.Common.ExecCmd import exec_cmd, ExecCmdFail
from lnst.Common.NetUtils import scan_netdevs
from lnst.Controller.Common import ControllerError

#this is a global object because opening the connection to libvirt in every
#object instance that uses it sometimes fails - the libvirt server probably
#can't handle that many connections at a time
_libvirt_conn = None

def init_libvirt_con():
    global _libvirt_conn
    if _libvirt_conn is None:
        _libvirt_conn = libvirt.open(None)

class VirtUtilsError(ControllerError):
    pass

def _ip(cmd):
    try:
        exec_cmd("ip %s" % cmd)
    except ExecCmdFail as err:
        raise VirtUtilsError("ip command error: %s" % err)

def _brctl(cmd):
    try:
        exec_cmd("brctl %s" % cmd)
    except ExecCmdFail as err:
        raise VirtUtilsError("brctl error: %s" % err)

def _iptables(cmd):
    try:
        exec_cmd("iptables %s" % cmd)
    except ExecCmdFail as err:
        raise VirtUtilsError("iptables error: %s" % err)

def _ip6tables(cmd):
    try:
        exec_cmd("ip6tables %s" % cmd)
    except ExecCmdFail as err:
        raise VirtUtilsError("ip6tables error: %s" % err)

def _virsh(cmd):
    try:
        exec_cmd("virsh %s" % cmd, log_outputs=False)
    except ExecCmdFail as err:
        raise VirtUtilsError("virsh error: %s" % err)

class VirtDomainCtl:
    _net_device_template = """
    <interface type='network'>
        <mac address='{0}'/>
        <source network='{1}'/>
        <model type='{2}'/>
    </interface>
    """
    _net_device_bare_template = """
    <interface>
        <mac address='{0}'/>
    </interface>
    """

    def __init__(self, domain_name):
        self._name = domain_name
        self._created_interfaces = {}

        init_libvirt_con()

        try:
            self._domain = _libvirt_conn.lookupByName(domain_name)
        except:
            raise VirtUtilsError("Domain '%s' doesn't exist!" % domain_name)

    def start(self):
        self._domain.create()

    def stop(self):
        self._domain.destroy()

    def restart(self):
        self._domain.reboot()

    def attach_interface(self, hw_addr, net_name, driver="virtio"):
        try:
            device_xml = self._net_device_template.format(hw_addr,
                                                          net_name,
                                                          driver)
            self._domain.attachDevice(device_xml)
            logging.debug("libvirt device with hwaddr '%s' "
                          "driver '%s' attached" % (hw_addr, driver))
            self._created_interfaces[hw_addr] = device_xml
            return True
        except libvirtError as e:
            raise VirtUtilsError(str(e))

    def detach_interface(self, hw_addr):
        if hw_addr in self._created_interfaces:
            device_xml = self._created_interfaces[hw_addr]
        else:
            device_xml = self._net_device_bare_template.format(hw_addr)

        try:
            self._domain.detachDevice(device_xml)
            logging.debug("libvirt device with hwaddr '%s' detached" % hw_addr)
            return True
        except libvirtError as e:
            raise VirtUtilsError(str(e))

    @classmethod
    def domain_exist(cls, domain_name):
        try:
            _libvirt_conn.lookupByName(domain_name)
            return True
        except:
            return False

class NetCtl(object):
    def __init__(self, name):
        self._name = name

    def get_name(self):
        return self._name

    def init(self):
        pass

    def cleanup(self):
        pass

class VirtNetCtl(NetCtl):
    _network_template = """
    <network ipv6='yes'>
        <name>{0}</name>
        <bridge name='virbr_{0}' stp='off' delay='0' />
        <domain name='{0}'/>
    </network>
    """

    def __init__(self, name=None):
        init_libvirt_con()

        if not name:
            name = self._generate_name()
        self._name = name

    def _generate_name(self):
        devs = _libvirt_conn.listNetworks()

        index = 0
        while True:
            name = "lnst_net%d" % index
            index += 1
            if name not in devs:
                return name

    def init(self):
        try:
            network_xml = self._network_template.format(self._name)
            _libvirt_conn.networkCreateXML(network_xml)
            logging.debug("libvirt network '%s' created" % self._name)
            return True
        except libvirtError as e:
            raise VirtUtilsError(str(e))

    def cleanup(self):
        try:
            network = _libvirt_conn.networkLookupByName(self._name)
            network.destroy()
            logging.debug("libvirt network '%s' destroyed" % self._name)
            return True
        except libvirtError as e:
            raise VirtUtilsError(str(e))

    @classmethod
    def network_exist(cls, net_name):
        try:
            _libvirt_conn.networkLookupByName(net_name)
            return True
        except:
            return False

class BridgeCtl(NetCtl):
    def __init__(self, name=None):
        if not name:
            name = self._generate_name()

        self._check_name(name)
        self._name = name
        self._remove = False

    def get_name(self):
        return self._name

    def set_remove(self, remove):
        self._remove = remove

    @staticmethod
    def _check_name(name):
        if len(name) > 16:
            msg = "Bridge name '%s' longer than 16 characters" % name
            raise VirtUtilsError(msg)

    @staticmethod
    def _generate_name():
        devs = scan_netdevs()

        index = 0
        while True:
            name = "lnstbr%d" % index
            index += 1
            unique = True
            for dev in devs:
                if name == dev["name"]:
                    unique = False
                    break

            if unique:
                return name

    def _exists(self):
        devs = scan_netdevs()
        for dev in devs:
            if self._name == dev["name"]:
                return True

        return False

    def init(self):
        if not self._exists():
            _brctl("addbr %s" % self._name)
            _iptables("-I FORWARD 1 -j REJECT -i %s -o any" % self._name)
            _iptables("-I FORWARD 1 -j REJECT -i any -o %s" % self._name)
            _iptables("-I FORWARD 1 -j ACCEPT -i %s -o %s" %
                                                    (self._name, self._name))
            _ip6tables("-I FORWARD 1 -j REJECT -i %s -o any" % self._name)
            _ip6tables("-I FORWARD 1 -j REJECT -i any -o %s" % self._name)
            _ip6tables("-I FORWARD 1 -j ACCEPT -i %s -o %s" %
                                                    (self._name, self._name))
            self._remove = True

        _ip("link set %s up" % self._name)

    def cleanup(self):
        if self._remove:
            _ip("link set %s down" % self._name)
            _brctl("delbr %s" % self._name)
            _iptables("-D FORWARD -j REJECT -i %s -o any" % self._name)
            _iptables("-D FORWARD -j REJECT -i any -o %s" % self._name)
            _iptables("-D FORWARD -j ACCEPT -i %s -o %s" %
                                                    (self._name, self._name))
            _ip6tables("-D FORWARD -j REJECT -i %s -o any" % self._name)
            _ip6tables("-D FORWARD -j REJECT -i any -o %s" % self._name)
            _ip6tables("-D FORWARD -j ACCEPT -i %s -o %s" %
                                                    (self._name, self._name))
