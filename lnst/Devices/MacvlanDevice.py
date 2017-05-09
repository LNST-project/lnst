"""
Defines the MacvlanDevice class

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Common.ExecCmd import exec_cmd
from lnst.Devices.SoftDevice import SoftDevice

class MacvlanDevice(SoftDevice):
    _name_template = "t_macvlan"

    def __init__(self, ifmanager, *args, **kwargs):
        super(MacvlanDevice, self).__init__(ifmanager, args, kwargs)

        self._real_dev = kwargs["realdev"]
        self._mode = kwargs.get("mode", None)
        self._hwaddr = kwargs.get("hwaddr", None)

    def create(self):
        create_cmd = "ip link add link {} {}".format(self._real_dev.name,
                                                     self.name)

        if self._hwaddr is not None:
            create_cmd += " address {}".format(self._hwaddr)

        if self._mode is not None:
            create_cmd += " mode {}".format(self._mode)

        create_cmd += " type macvlan"

        exec_cmd(create_cmd)
