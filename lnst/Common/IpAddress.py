"""
Defines BaseIpAddress and derived classes and the IpAddress factory method.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import socket
from collections.abc import Iterator
from ipaddress import IPv4Network, IPv6Network, IPv4Interface, IPv6Interface, ip_interface, IPv4Address, IPv6Address
from itertools import dropwhile, islice
from socket import inet_pton, inet_ntop, AF_INET, AF_INET6
from typing import Union, Optional

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


def interface_addresses(
        network: Union[IPv4Network, IPv6Network],
        default_start: Optional[Union[str, IPv4Interface, IPv6Interface]] = None,
        default_skip: Optional[int] = None,
) -> Iterator[BaseIpAddress]:
    """
    Generator of BaseIpAddress objects. Used to allocate interface addresses
    (host IP + prefix length) from a network.

    When used together with `NetworkParam` it provides a convenient way to
    generate network addresses for the host interfaces used in LNST recipes.

    If `default_start` is specified it is passed to `ipaddress.ip_interface()`
    if that interface is in `network` the iteration will start at that address.

    `default_skip` (only used when `default_start` is specified) allows you to
    skip every N addresses, it's passed to `itertools.islice`.
    """
    hosts = network.hosts()
    if default_start:
        default_start = ip_interface(default_start)
        if default_start in network:
            hosts = dropwhile(lambda x: x != default_start.ip, hosts)
            if default_skip:
                hosts = islice(hosts, 0, None, default_skip)

    for addr in hosts:
        yield ipaddress(f"{addr}/{network.prefixlen}")


def ipaddress(addr, flags=None):
    """Factory method to create a BaseIpAddress object"""
    if isinstance(addr, BaseIpAddress):
        return addr
    elif isinstance(addr, str):
        try:
            return Ip4Address(addr, flags)
        except:
            return Ip6Address(addr, flags)
    elif isinstance(addr, IPv4Address):
        return Ip4Address(str(addr), flags)
    elif isinstance(addr, IPv6Address):
        return Ip6Address(str(addr), flags)
    else:
        raise LnstError("Value must be a BaseIpAddress or string object."
                        " Not {}".format(type(addr)))


def ip_version_string(ip_address: BaseIpAddress) -> str:
    return "ipv4" if isinstance(ip_address, Ip4Address) else "ipv6"

