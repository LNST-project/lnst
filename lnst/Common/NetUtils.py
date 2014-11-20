"""
Networking related utilities and common code

Copyright 2012 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import os
import re
import socket
import subprocess
from pyroute2 import IPRSocket
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink import NLM_F_DUMP
from pyroute2.netlink import NLMSG_DONE
from pyroute2.netlink import NLMSG_ERROR
try:
    from pyroute2.netlink.iproute import RTM_GETLINK
    from pyroute2.netlink.iproute import RTM_NEWLINK
except ImportError:
    from pyroute2.iproute import RTM_GETLINK
    from pyroute2.iproute import RTM_NEWLINK
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg


def normalize_hwaddr(hwaddr):
    try:
        return hwaddr.upper().rstrip("\n")
    except:
        return ""


def scan_netdevs():
    scan = []
    nl_socket = IPRSocket()
    msg = ifinfmsg()
    msg["family"] = socket.AF_UNSPEC
    msg["header"]["type"] = RTM_GETLINK
    msg["header"]["flags"] = NLM_F_REQUEST | NLM_F_DUMP
    msg["header"]["pid"] = os.getpid()
    msg["header"]["sequence_number"] = 1
    msg.encode()

    nl_socket.sendto(msg.buf.getvalue(), (0, 0))

    finished = False
    while not finished:
        parts = nl_socket.get()
        for part in parts:
            if part["header"]["type"] in [NLMSG_DONE, NLMSG_ERROR]:
                finished = True
                continue
            if part["header"]["sequence_number"] != 1:
                continue

            if part["header"]["type"] == RTM_NEWLINK:
                new_link = {}
                new_link["netlink_msg"] = part
                new_link["index"] = part["index"]
                new_link["name"] = part.get_attr("IFLA_IFNAME")

                hwaddr = part.get_attr("IFLA_ADDRESS")
                new_link["hwaddr"] = normalize_hwaddr(hwaddr)

                scan.append(new_link)

    nl_socket.close()
    return scan


def test_tcp_connection(host, port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        s.shutdown(socket.SHUT_RDWR)
        return True
    except:
        return False


def verify_ip_address(addr):
    if len(addr.split('.')) != 4:
        return False
    try:
        socket.inet_aton(addr)
        return True
    except:
        return False


def verify_mac_address(addr):
    if re.match("^[0-9a-f]{2}([:][0-9a-f]{2}){5}$", addr, re.I):
        return True
    else:
        return False


def get_corespond_local_ip(query_ip):
    """
    Get ip address in local system which can communicate with query_ip.

    @param query_ip: IP of client which want communicate with autotest machine.
    @return: IP address which can communicate with query_ip
    """
    query_ip = socket.gethostbyname(query_ip)
    ip = subprocess.Popen("ip route get %s" % (query_ip),
                          shell=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    ip = ip.communicate()[0]
    ip = re.search(r"src ([0-9.]*)", ip)
    if ip is None:
        return ip
    return ip.group(1)


class AddressPool:
    def __init__(self, start, end):
        self._next = self._addr_to_byte_string(start)
        self._final = self._addr_to_byte_string(end)

    def _inc_byte_string(self, byte_string):
        if len(byte_string):
            byte_string[-1] += 1
            if byte_string[-1] > 255:
                del byte_string[-1]
                self._inc_byte_string(byte_string)
                byte_string.append(0)

    def _addr_to_byte_string(self, addr):
        pass

    def _byte_string_to_addr(self, byte_string):
        pass

    def get_addr(self):
        if self._next > self._final:
            msg = "Pool exhausted, no free addresses available"
            raise Exception(msg)

        addr_str = self._byte_string_to_addr(self._next)
        self._inc_byte_string(self._next)

        return addr_str


class MacPool(AddressPool):
    def _addr_to_byte_string(self, addr):
        if not verify_mac_address(addr):
            raise Exception("Invalid MAC address")

        bs = [int(byte, 16) for byte in addr.split(":")]

        return bs

    def _byte_string_to_addr(self, byte_string):
        return ':'.join(map(lambda x: "%02x" % x, byte_string))


class IpPool(AddressPool):
    def _addr_to_byte_string(self, addr):
        if not verify_ip_address(addr):
            raise Exception("Invalid IP address")

        bs = [int(byte) for byte in addr.split(".")]

        return bs

    def _byte_string_to_addr(self, byte_string):
        return '.'.join(map(str, byte_string))
