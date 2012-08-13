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
import re
import socket
import subprocess

def normalize_hwaddr(hwaddr):
    return hwaddr.upper().rstrip("\n")

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
