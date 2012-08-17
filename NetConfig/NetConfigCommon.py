"""
This module defines common stuff for NetConfig

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

def get_slaves(netdev):
    try:
        return netdev["slaves"]
    except KeyError:
        return set()

def get_option(netdev, opt_name):
    try:
        options = netdev["options"]
    except KeyError:
        return None
    for option, value in options:
        if option == opt_name:
            return value
    return None
