"""
Utilities for manipulating virtualization host, its guests and
connections between them

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import logging
from lnst.Controller.Common import ControllerError

#this is a global object because opening the connection to libvirt in every
#object instance that uses it sometimes fails - the libvirt server probably
#can't handle that many connections at a time
_libvirt_conn = None

def init_libvirt_con():
    try:
        import libvirt
    except ModuleNotFoundError:
        msg = "Failed to import libvirt, please install the dependency if you want to use the libvirt network management feature."
        logging.error(msg)
        raise ControllerError(msg)

    global _libvirt_conn
    if _libvirt_conn is None:
        _libvirt_conn = libvirt.open(None)

class VirtDomainCtlError(ControllerError):
    pass

class VirtDomainCtl(object):
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
            raise VirtDomainCtlError("Domain '%s' doesn't exist!" % domain_name)

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
            self._created_interfaces[str(hw_addr)] = device_xml
            return True
        except libvirtError as e:
            raise VirtDomainCtlError(str(e))

    def detach_interface(self, hw_addr):
        if str(hw_addr) in self._created_interfaces:
            device_xml = self._created_interfaces[str(hw_addr)]
        else:
            device_xml = self._net_device_bare_template.format(hw_addr)

        try:
            self._domain.detachDevice(device_xml)
            logging.debug("libvirt device with hwaddr '%s' detached" % hw_addr)
            return True
        except libvirtError as e:
            raise VirtDomainCtlError(str(e))

    @classmethod
    def domain_exist(cls, domain_name):
        try:
            _libvirt_conn.lookupByName(domain_name)
            return True
        except:
            return False
