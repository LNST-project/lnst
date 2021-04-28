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
import socket
from socket import inet_pton, inet_ntop, AF_INET, AF_INET6
from lnst.Common.LnstError import LnstError

#TODO Replace this with Python's builtin ipaddress module.
# To make use of its IP address generators.
# https://docs.python.org/3/library/ipaddress.html#module-ipaddress

class BaseIpAddress(object):
    def __init__(self, addr, flags=None):
        self.addr, self.prefixlen = self._parse_addr(addr)

        self.flags = flags
        self.family = None

    def __str__(self):
        return str(inet_ntop(self.family, self.addr))

    def __eq__(self, other):
        try:
            # checks the type of the other object and also accepts comparisons
            # with compatible objects
            other = ipaddress(other)
        except:
            return False

        if self.addr != other.addr or\
           self.prefixlen != other.prefixlen:
            return False
        else:
            return True

    def __ne__(self, other):
        return not self.__eq__(other)

    @staticmethod
    def _parse_addr(addr):
        raise NotImplementedError()

    def __repr__(self):
        return "{}({}/{})".format(self.__class__.__name__, str(self), self.prefixlen)

    @property
    def is_tentative(self):
        #can only be True for IPv6 addresses
        return False

class Ip4Address(BaseIpAddress):
    def __init__(self, addr, flags=None):
        super(Ip4Address, self).__init__(addr, flags)

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
            addr = inet_pton(AF_INET, addr)
        except:
            raise LnstError("Invalid IPv4 format.")

        return addr, prefixlen

    @property
    def is_multicast(self):
        aton = socket.inet_aton
        return aton("224.0.0.0") <= self.addr <= aton("239.255.255.255")

class Ip6Address(BaseIpAddress):
    def __init__(self, addr, flags=None):
        super(Ip6Address, self).__init__(addr, flags)

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
            addr = inet_pton(AF_INET6, addr)
        except:
            raise LnstError("Invalid IPv6 format.")

        return addr, prefixlen

    @property
    def is_link_local(self):
        return self.addr[:8] == b'\xfe\x80\x00\x00\x00\x00\x00\x00'

    @property
    def is_multicast(self):
        return self.addr[:1] == b'\xff'

    @property
    def is_tentative(self):
        #constant from linux/if_addr.h
        IFA_F_TENTATIVE = 0x40
        return IFA_F_TENTATIVE & self.flags

def ipaddress(addr, flags=None):
    """Factory method to create a BaseIpAddress object"""
    if isinstance(addr, BaseIpAddress):
        return addr
    elif isinstance(addr, str):
        try:
            return Ip4Address(addr, flags)
        except:
            return Ip6Address(addr, flags)
    else:
        raise LnstError("Value must be a BaseIpAddress or string object."
                        " Not {}".format(type(addr)))
