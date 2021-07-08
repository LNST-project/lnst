from enum import IntFlag
from typing import Dict

from pyroute2 import MPTCP
from pyroute2.netlink.generic.mptcp import mptcp_msg
from socket import AF_INET, AF_INET6
from dataclasses import dataclass
from lnst.Common.IpAddress import ipaddress, BaseIpAddress

class MPTCPFlags(IntFlag):
    # via https://github.com/torvalds/linux/blob/9d31d2338950293ec19d9b095fbaa9030899dcb4/include/uapi/linux/mptcp.h#L73
    MPTCP_PM_ADDR_FLAG_SIGNAL = (1 << 0)
    MPTCP_PM_ADDR_FLAG_SUBFLOW = (1 << 1)
    MPTCP_PM_ADDR_FLAG_BACKUP = (1 << 2)

#@dataclass
class MPTCPEndpoint:
    # id: int
    # ip_address: BaseIpAddress
    # flags: int



    @classmethod
    def from_netlink(cls, msg: mptcp_msg):
        """
        ..code py
        >>> r = mptcp.endpoint('show')[0]
        >>> type(r)
        <class 'pyroute2.netlink.generic.mptcp.mptcp_msg'>
        >>> r
        {'cmd': 3, 'version': 1, 'reserved': 0, 'attrs': [('MPTCP_PM_ATTR_ADDR', {'attrs': [('MPTCP_PM_ADDR_ATTR_FAMILY', 2), ('MPTCP_PM_ADDR_ATTR_ID', 5), ('MPTCP_PM_ADDR_ATTR_FLAGS', 1), ('MPTCP_PM_ADDR_ATTR_ADDR4', '192.168.202.1')]}, 32768)], 'header': {'length': 56, 'type': 27, 'flags': 2, 'sequence_number': 257, 'pid': 26782, 'error': None, 'target': 'localhost', 'stats': Stats(qsize=0, delta=0, delay=0)}}
        >>> a = r.get_attr("MPTCP_PM_ATTR_ADDR")
        >>> type(a)
        <class 'pyroute2.netlink.generic.mptcp.mptcp_msg.pm_addr'>
        >>> a
        {'attrs': [('MPTCP_PM_ADDR_ATTR_FAMILY', 2), ('MPTCP_PM_ADDR_ATTR_ID', 5), ('MPTCP_PM_ADDR_ATTR_FLAGS', 1), ('MPTCP_PM_ADDR_ATTR_ADDR4', '192.168.202.1')]}
        :param msg:
        :return:
        """

        addr = msg.get_attr("MPTCP_PM_ATTR_ADDR")
        ep_id = addr.get_attr("MPTCP_PM_ADDR_ATTR_ID")
        ip_type = addr.get_attr("MPTCP_PM_ADDR_ATTR_FAMILY")
        flags = addr.get_attr("MPTCP_PM_ADDR_ATTR_FLAGS")

        if ip_type == AF_INET:
            ip = ipaddress(addr.get_attr("MPTCP_PM_ADDR_ATTR_ADDR4"))
        else:
            ip = ipaddress(addr.get_attr("MPTCP_PM_ADDR_ATTR_ADDR6"))

        return cls(ep_id, ip, flags)

    @classmethod
    def from_netlink_new(cls, nl_msg):
        addr = nl_msg.get_attr("MPTCP_PM_ATTR_ADDR")
        addr_attr = dict(addr['attrs'])
        return cls(addr_attr)

    def __init__(self, attr: Dict):
        self._attr = attr
        self._ip = None
        self._flags = None

    @property
    def id(self):
        return self._attr['MPTCP_PM_ADDR_ATTR_ID']

    @property
    def ip_address(self):
        if self._ip is None:
            if self.ip_family == AF_INET:
                self._ip = ipaddress(self._attr['MPTCP_PM_ADDR_ATTR_ADDR4'])
            else:
                self._ip = ipaddress(self._attr['MPTCP_PM_ADDR_ATTR_ADDR6'])
        return self._ip

    @property
    def ip_family(self):
        return self._attr['MPTCP_PM_ADDR_ATTR_FAMILY']

    @property
    def flags(self):
        if self._flags is None:
            self._flags = MPTCPFlags(self._attr['MPTCP_PM_ADDR_ATTR_FLAGS'])
        return self._flags

    @property
    def is_signal(self):
        return MPTCPFlags.MPTCP_PM_ADDR_FLAG_SIGNAL in self.flags

    @property
    def is_subflow(self):
        return MPTCPFlags.MPTCP_PM_ADDR_FLAG_SIGNAL in self.flags

    @property
    def is_backup(self):
        return MPTCPFlags.MPTCP_PM_ADDR_FLAG_BACKUP in self.flags


class MPTCPManager:
    def __init__(self):
        self._mptcp = MPTCP()
        self._endpoints = {}

    @property
    def endpoints(self):
        self._endpoints = {}
        nl_eps = self._mptcp.endpoint('show')
        for nl_ep in nl_eps:
            ep = MPTCPEndpoint.from_netlink(nl_ep)
            self._endpoints[ep.id] = ep
        return self._endpoints



    def add_endpoints(self, endpoint_ips):
        for ip in endpoint_ips:
            self._mptcp.endpoint("add", addr=str(ip))

    def delete_all(self):
        r = self._mptcp.endpoint("flush")
        return r

