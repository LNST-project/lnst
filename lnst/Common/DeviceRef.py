"""
Defines the DeviceRef class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

class DeviceRef(object):
    """Device reference transferable over network

    Used in Controller-Agent communication protocol.
    """
    def __init__(self, ifindex):
        self.ifindex = int(ifindex)
