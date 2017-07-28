"""
Defines the VtiDevice and Vti6Device classes.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Common.ExecCmd import exec_cmd
from lnst.Devices.Device import DeviceError
from lnst.Devices.SoftDevice import SoftDevice

class _BaseVtiDevice(SoftDevice):
    def __init__(self, ifmanager, *args, **kwargs):
        super(_BaseVtiDevice, self).__init__(ifmanager, args, kwargs)

        self._key = kwargs["key"]
        self._local = kwargs.get("local", None)
        self._remote = kwargs.get("remote", None)
        self._device = kwargs.get("dev", None)

        if self.local is None and self.remote is None:
            raise DeviceError("One of local/remote MUST be defined.")

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
        raise NotImplementedError

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
                        key=" key " + self.key,
                        device=(" dev " + self.device.name
                                if self.device
                                else "")))


class VtiDevice(_BaseVtiDevice):
    vti_type = "vti"
    _name_template = "t_vti"

class Vti6Device(_BaseVtiDevice):
    vti_type = "vti6"
    _name_template = "t_ip6vti"
