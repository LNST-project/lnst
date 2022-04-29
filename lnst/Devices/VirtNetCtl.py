"""
Defines the VirtNetCtl class used for dynamically adding and removing network
interface cards to libvirt guests.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import logging
from lnst.Common.LnstError import LnstError

#this is a global object because opening the connection to libvirt in every
#object instance that uses it sometimes fails - the libvirt server probably
#can't handle that many connections at a time
_libvirt_conn = None

def init_libvirt_con():
    try:
        import libvirt
    except ModuleNotFoundError:
        msg = "Failed to import libvirt, please install libvirt to use the libvirt network management features."
        logging.error(msg)
        raise LnstError(msg)

    global _libvirt_conn
    if _libvirt_conn is None:
        _libvirt_conn = libvirt.open(None)

class VirtNetCtlError(LnstError):
    pass

class VirtNetCtl(object):
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

    def get_name(self):
        return self._name

    def init(self):
        try:
            network_xml = self._network_template.format(self._name)
            _libvirt_conn.networkCreateXML(network_xml)
            logging.debug("libvirt network '%s' created" % self._name)
            return True
        except libvirtError as e:
            raise VirtNetCtlError(str(e))

    def cleanup(self):
        try:
            network = _libvirt_conn.networkLookupByName(self._name)
            network.destroy()
            logging.debug("libvirt network '%s' destroyed" % self._name)
            return True
        except libvirtError as e:
            raise VirtNetCtlError(str(e))

    @classmethod
    def network_exist(cls, net_name):
        try:
            _libvirt_conn.networkLookupByName(net_name)
            return True
        except:
            return False
