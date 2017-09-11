"""
Defines the VtiDevice and Vti6Device classes.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import pyroute2
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.IpAddress import ipaddress
from lnst.Common.ExecCmd import exec_cmd
from lnst.Common.DeviceError import DeviceError, DeviceConfigError
from lnst.Devices.Device import Device
from lnst.Devices.SoftDevice import SoftDevice

class _BaseVtiDevice(SoftDevice):
    def __init__(self, ifmanager, *args, **kwargs):
        super(_BaseVtiDevice, self).__init__(ifmanager, args, kwargs)

        self._key = int(kwargs["key"])

        self._local = kwargs.get("local", None)
        if self._local:
            self._local = ipaddress(self._local)

        self._remote = kwargs.get("remote", None)
        if self._remote:
            self._remote = ipaddress(self._remote)

        self._device = kwargs.get("dev", None)

        if self._device is not None and not isinstance(self._device, Device):
            raise DeviceError("dev parameter must be a Device object.")

        if self.local is None and self.remote is None:
            raise DeviceError("One of local/remote MUST be defined.")

    def _restore_original_data(self):
        """Restores initial configuration from stored values"""
        self.mtu = self._orig_mtu
        self.name = self._orig_name

    @property
    def key(self):
        return self._key

    @property
    def local(self):
        return self._local

    @property
    def remote(self):
        return self._remote

    @property
    def device(self):
        return self._device

    @property
    def vti_type(self):
        raise NotImplementedError()

    # TODO this method is tested as not working, maybe pyroute2 support is
    # missing...
    # def _create(self):
        # with pyroute2.IPRoute() as ipr:
            # try:
                # kwargs = {}
                # if self.local:
                    # kwargs["IFLA_VTI_LOCAL"] = str(self.local)

                # if self.remote:
                    # kwargs["IFLA_VTI_REMOTE"] = str(self.remote)

                # if self.device:
                    # kwargs["IFLA_VTI_LINK"] = self.device.ifindex

                # ipr.link("add", IFLA_IFNAME=self.name,
                         # IFLA_INFO_KIND=self._link_type,
                         # IFLA_VTI_IKEY=self.key,
                         # IFLA_VTI_OKEY=self.key,
                         # **kwargs)
                # self._if_manager.handle_netlink_msgs()
            # except pyroute2.netlink.NetlinkError:
                # log_exc_traceback()
                # raise DeviceConfigError("Creating link %s failed." % self.name)

    def _create(self):
        exec_cmd("ip link add {name} type {type}{local}{remote}{key}{device}".
                 format(name=self.name,
                        type=self.vti_type,
                        local=(" local " + str(self.local)
                               if self.local
                               else ""),
                        remote=(" remote " + str(self.remote)
                                if self.remote
                                else ""),
                        key=" key " + str(self.key),
                        device=(" dev " + self.device.name
                                if self.device
                                else "")))


class VtiDevice(_BaseVtiDevice):
    vti_type = "vti"
    _name_template = "t_vti"

class Vti6Device(_BaseVtiDevice):
    vti_type = "vti6"
    _name_template = "t_ip6vti"
