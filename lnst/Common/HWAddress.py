"""
Defines HWAddress class and the hwaddress factory method.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import re
from lnst.Common.LnstError import LnstError

class HWAddress(object):
    def __init__(self, addr):
        self.addr = self._parse_addr(addr)

    def __str__(self):
        hex_list = ['%0.2X' % x for x in self.addr]
        return ":".join(hex_list)

    def __eq__(self, other):
        if len(other.addr) != len(self.addr):
            return False

        for i in range(len(self.addr)):
            if self.addr[i] != other.addr[i]:
                return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def _parse_addr(self, addr):
        tmp_list = addr.split(':')
        if len(tmp_list) != 6:
            raise LnstError("Invalid HWAddress format")

        res = []
        for i in tmp_list:
            val = int(i, 16)
            if val > 255 or val < 0:
                raise LnstError("Invalid HWAddress format")
            res.append(val)
        return res

def hwaddress(addr):
    """Factory method to create a _HWAddress object"""
    if isinstance(addr, HWAddress):
        return addr
    elif isinstance(addr, str):
        return HWAddress(addr)
    else:
        raise LnstError("Value must be a HWAddress or string object."
                        " Not {}".format(type(addr)))
