"""
Defines the VirtualDevice class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import logging
from time import sleep
from lnst.Common.Utils import check_process_running
from lnst.Common.NetUtils import normalize_hwaddr
from lnst.Devices.Device import Device, DeviceError
from lnst.Devices.RemoteDevice import RemoteDevice

# conditional support for libvirt
if check_process_running("libvirtd"):
    from lnst.Controller.VirtUtils import VirtNetCtl

class VirtualDevice(RemoteDevice):
    """Remote eth device created on the controller through libvirt

    To support creation of new devices on virtual machines, we derive from
    the RemoteDevice class and override the create method (which would be
    remotely called on the slave for the Device class type). Instead, the
    create method is called on the controller where libvirt is running.

    The Tester shouldn't create instances of this class. They're created
    automatically if matching virtual machines is allowed.

    Theoretically if a match is virtual the tester could also dynamically add
    devices during test execution, however this is NOT SUPPORTED at the moment.
    """
    def __init__(self, network, driver=None, hwaddr=None):
        super(VirtualDevice, self).__init__(Device, None, None)

        self.virt_driver = driver if driver is not None else "virtio"
        self.orig_hwaddr = hwaddr
        self._network = network

    @property
    def network(self):
        return self._network

    @network.setter
    def network(self, network):
        self._network = network

    def _match_update_data(self, data):
        if self.orig_hwaddr == data["hwaddr"]:
            return True

        return super(VirtualDevice, self)._match_update_data(data)

    def create(self):
        domain_ctl = self.host.get_domain_ctl()

        if self.orig_hwaddr:
            if self.host.get_dev_by_hwaddr(self.orig_hwaddr):
                msg = "Device with hwaddr %s already exists" % self.orig_hwaddr
                raise DeviceError(msg)
        else:
            mac_pool = self.host.get_mac_pool()
            while True:
                hwaddr = normalize_hwaddr(mac_pool.get_addr())
                if not self.host.get_dev_by_hwaddr(hwaddr):
                    self.orig_hwaddr = hwaddr
                    break

        bridges = self.host.get_network_bridges()
        if self.network in bridges:
            net_ctl = bridges[self.network]
        else:
            bridges[self.network] = net_ctl = VirtNetCtl()
            net_ctl.init()

        net_name = net_ctl.get_name()

        logging.info("Creating virtual device with hwaddr='%s' on machine %s",
                     self.orig_hwaddr, self.host.get_id())

        domain_ctl.attach_interface(self.orig_hwaddr,
                                    net_name,
                                    self.virt_driver)
        # The sleep here is necessary, because udev sometimes renames the
        # newly created device
        sleep(1)

    def destroy(self):
        logging.info("Destroying virtual device with hwaddr='%s' on machine %s",
                     self.orig_hwaddr, self.host.get_id())

        domain_ctl = self.host.get_domain_ctl()
        domain_ctl.detach_interface(self.orig_hwaddr)
