import logging
import libvirt
from libvirt import libvirtError
from lnst.Common.LnstError import LnstError
from lnst.Common.Logs import log_exc_traceback

class LibvirtControl(object):
    def __init__(self):
        self._libvirt_conn = libvirt.open(None)

    def createXML(self, xml, flags=0):
        try:
            self._libvirt_conn.createXML(xml, flags)
        except:
            log_exc_traceback()

    def vm_start(self, name):
        vm = self._libvirt_conn.lookupByName(name)
        vm.create()

    def vm_shutdown(self, name):
        vm = self._libvirt_conn.lookupByName(name)
        try:
            vm.shutdown()
        except:
            log_exc_traceback()

    def vm_destroy(self, name):
        vm = self._libvirt_conn.lookupByName(name)
        try:
            vm.destroy()
        except:
            log_exc_traceback()

    def vm_XMLDesc(self, name):
        vm = self._libvirt_conn.lookupByName(name)
        return vm.XMLDesc()

    def is_vm_running(self, name):
        vm = self._libvirt_conn.lookupByName(name)
        return vm.isActive()
