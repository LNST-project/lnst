from lnst.Common.Logs import log_exc_traceback
from lnst.Common.DependencyError import DependencyError


class LibvirtControl(object):
    def __init__(self):
        try:
            import libvirt
        except ModuleNotFoundError as e:
            raise DependencyError(e)

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
