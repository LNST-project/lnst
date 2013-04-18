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

import os
import re
import copy
import time
import logging
from tempfile import NamedTemporaryFile
from xml.dom import minidom
from lnst.Common.ExecCmd import exec_cmd, ExecCmdFail
from lnst.Common.NetUtils import normalize_hwaddr, scan_netdevs

class VirtUtilsError(Exception):
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

def _virsh(cmd):
    try:
        exec_cmd("virsh %s" % cmd)
    except ExecCmdFail as err:
        raise VirtUtilsError("virsh error: %s" % err)

# TODO: This class should use the python bindings to libvirt,
# not the virsh CLI interface
class VirtDomainCtl:
    _name = None

    def __init__(self, domain_name):
        self._name = domain_name

    def start(self):
        _virsh("start %s" % self._name)

    def stop(self):
        _virsh("destroy %s" % self._name)

    def restart(self):
        _virsh("reboot %s" % self._name)

    def attach_interface(self, hwaddr, net_name, net_type="bridge"):
        _virsh("attach-interface %s %s %s --mac %s" % \
                            (self._name, net_type, net_name, hwaddr))
        self.ifup(hwaddr)

    def detach_interface(self, hwaddr, net_type="bridge"):
        _virsh("detach-interface %s %s %s" % (self._name, net_type, hwaddr))

    def ifup(self, hwaddr):
        _virsh("domif-setlink %s %s up" % (self._name, hwaddr))

    def ifdown(self, hwaddr):
        _virsh("domif-setlink %s %s down" % (self._name, hwaddr))

class NetCtl(object):
    _name = None

    def __init__(self, name):
        self._name = name

    def get_name(self):
        return self._name

    def init(self):
        pass

    def cleanup(self):
        pass

class VirtNetCtl(NetCtl):
    _addr = None
    _mask = None

    _dhcp_from = None
    _dhcp_to = None
    _static_mappings = []
    _lease_file = None

    def setup_dhcp_server(self, addr, mask, range_start, range_end,
                                    static_map=None):
        self._addr = addr
        self._mask = mask
        self._dhcp_from = range_start
        self._dhcp_to = range_end
        self._lease_file = "/var/lib/libvirt/dnsmasq/%s.leases" % self._name
        if static_map:
            self._static_mappings = static_map

    def get_dhcp_mapping(self, hwaddr, timeout=30):
        wait = timeout
        while True:
            addr = self._get_map(hwaddr)
            if addr or not wait:
                break

            time.sleep(1)
            wait -= 1

        return addr

    def _get_map(self, hwaddr):

        try:
            leases_file = open(self._lease_file, "r")
        except IOError as err:
            raise VirtUtilsError("Unable to resolve IP mapping (%s)" % err)

        addr = None
        normalized_hwaddr = normalize_hwaddr(hwaddr)
        for entry in leases_file:
            match = re.match(r"\d+\s+([0-9a-f:]+)\s+([0-9\.]+)", entry)
            if match:
                entry_hwaddr = normalize_hwaddr(match.group(1))
                entry_addr = match.group(2)
                if entry_hwaddr == normalized_hwaddr:
                    addr = entry_addr
                    break

        leases_file.close()
        return addr


    def init(self):
        tmp_file = NamedTemporaryFile(delete=False)
        doc = self._get_net_xml_dom()

        doc.writexml(tmp_file)
        tmp_file.close()

        _virsh("net-create %s" % tmp_file.name)
        os.unlink(tmp_file.name)

    def cleanup(self):
        _virsh("net-destroy %s" % self._name)
        exec_cmd("rm -f %s" % self._lease_file)

    def _get_net_xml_dom(self):
        doc = minidom.Document()

        net = doc.createElement("network")
        doc.appendChild(net)

        name = doc.createElement("name")
        name_text = doc.createTextNode(self._name)
        name.appendChild(name_text)
        net.appendChild(name)

        if self._addr:
            ip = doc.createElement("ip")
            ip.setAttribute("address", self._addr)
            ip.setAttribute("netmask", self._mask)
            net.appendChild(ip)

            dhcp = doc.createElement("dhcp")
            ip.appendChild(dhcp)

            dhcp_range = doc.createElement("range")
            dhcp_range.setAttribute("start", self._dhcp_from)
            dhcp_range.setAttribute("end", self._dhcp_to)
            dhcp.appendChild(dhcp_range)

            for mapping in self._static_mappings:
                hwaddr, addr = mapping
                host = doc.createElement("host")
                host.setAttribute("mac", hwaddr)
                host.setAttribute("ip", addr)
                dhcp.appendChild(host)

        return doc

class BridgeCtl(NetCtl):
    _remove = False

    def __init__(self, name=None):
        if not name:
            name = self._generate_name()

        self._check_name(name)
        self._name = name

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
            self._remove = True

        _ip("link set %s up" % self._name)

    def cleanup(self):
        if self._remove:
            _ip("link set %s down" % self._name)
            _brctl("delbr %s" % self._name)
