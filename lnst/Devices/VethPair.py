"""
Defines the VethPair factory method.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Devices.VethDevice import VethDevice, PairedVethDevice
from lnst.Devices.RemoteDevice import RemoteDevice, PairedRemoteDevice

def VethPair(*args, **kwargs):
    """Creates a pair of Veth Devices

    Args:
        args, kwargs passed to the VethDevice constructor on the Slave.
    """
    first = RemoteDevice(VethDevice, args, kwargs)
    second = PairedRemoteDevice(first, PairedVethDevice)
    return (first, second)
