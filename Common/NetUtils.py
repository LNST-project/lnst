"""
Networking related utilities and common code

Copyright 2012 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import logging
import os
import re
import socket
import subprocess

def normalize_hwaddr(hwaddr):
    return hwaddr.upper().rstrip("\n")

def scan_netdevs():
    sys_dir = "/sys/class/net"
    scan = []
    for root, dirs, files in os.walk(sys_dir):
        if "lo" in dirs:
            dirs.remove("lo")
        for d in dirs:
            dev_path = os.path.join(sys_dir, d)
            addr_path = os.path.join(dev_path, "address")
            if not os.path.isfile(addr_path):
                continue
            handle = open(addr_path, "rb")
            addr = handle.read()
            handle.close()
            addr = normalize_hwaddr(addr)
            scan.append({"name": d, "hwaddr": addr})
    return scan

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
    ip = re.search(r"src ([0-9.]*)",ip)
    if ip is None:
        return ip
    return ip.group(1)
