"""
Defines the BridgeDevice class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Common.ExecCmd import exec_cmd
from lnst.Devices.MasterDevice import MasterDevice

class BridgeDevice(MasterDevice):
    _name_template = "t_br"

    def _create(self):
        exec_cmd("ip link add dev {} type bridge".format(self._name))

    def _get_bridge_dir(self):
        return "/sys/class/net/%s/bridge" % self.name

    def set_option(self, option, value):
        #TODO redo to work with iproute
        exec_cmd('echo "%s" > %s/%s' % (value,
                                        self._get_bridge_dir(),
                                        option))

    def set_options(self, options):
        for option, value in options:
            self.set_option(option, value)
