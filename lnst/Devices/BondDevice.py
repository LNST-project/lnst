"""
Defines the BondDevice class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Common.ExecCmd import exec_cmd
from lnst.Devices.MasterDevice import MasterDevice

class BondDevice(MasterDevice):
    _name_template = "t_bond"

    def _create(self):
        exec_cmd("ip link add %s type bond" % self.name)

    def _get_bond_dir(self):
        return "/sys/class/net/%s/bonding" % self.name

    def set_option(self, option, value):
        if option == "primary":
            '''
            "primary" option is not direct value but it's
            a Device reference
            '''
            value = value.name
        exec_cmd('echo "%s" > %s/%s' % (value,
                                        self._get_bond_dir(),
                                        option))

    def set_options(self, options):
        for option, value in options:
            self.set_option(option, value)
