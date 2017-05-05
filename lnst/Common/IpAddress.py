"""
Defines BaseIpAddress and derived classes and the IpAddress factory method.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import re
from socket import inet_pton, AF_INET, AF_INET6
from lnst.Common.LnstError import LnstError

class BaseIpAddress(object):
    def __init__(self, addr):
        self.addr, self.prefixlen = self._parse_addr(addr)

        self.family = None

    def __str__(self):
        return str(self.addr)

    def __eq__(self, other):
        if self.addr != other.addr or\
           self.prefixlen != other.prefixlen:
            return False
        else:
            return True

    @staticmethod
    def _parse_addr(addr):
        raise NotImplementedError()

class Ip4Address(BaseIpAddress):
    def __init__(self, addr):
        super(Ip4Address, self).__init__(addr)

        self.family = AF_INET

    @staticmethod
    def _parse_addr(addr):
        addr = addr.split('/')
        if len(addr) == 1:
            addr = addr[0]
            prefixlen = 32
        elif len(addr) == 2:
            addr, prefixlen = addr
            prefixlen = int(prefixlen)
        else:
            raise LnstError("Invalid IPv4 format.")

        try:
            inet_pton(AF_INET, addr)
        except:
            raise LnstError("Invalid IPv4 format.")

        return addr, prefixlen

class Ip6Address(BaseIpAddress):
    def __init__(self, addr):
        super(Ip6Address, self).__init__(addr)

        self.family = AF_INET6

    @staticmethod
    def _parse_addr(addr):
        addr = addr.split('/')
        if len(addr) == 1:
            addr = addr[0]
            prefixlen = 128
        elif len(addr) == 2:
            addr, prefixlen = addr
            prefixlen = int(prefixlen)
        else:
            raise LnstError("Invalid IPv6 format.")

        try:
            type(inet_pton(AF_INET6, addr))
        except:
            raise LnstError("Invalid IPv6 format.")

        return addr, prefixlen

def IpAddress(addr):
    """Factory method to create a BaseIpAddress object"""
    if isinstance(addr, BaseIpAddress):
        return addr
    #TODO add switches for host, interface etc...
    elif isinstance(addr, str):
        try:
            return Ip4Address(addr)
        except:
            return Ip6Address(addr)
    else:
        raise LnstError("Value must be a BaseIpAddress or string object."
                        "Not {}".format(type(addr)))
