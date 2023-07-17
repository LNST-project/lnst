"""
Package for all LNST Test classes. It will contain all Test classes provided
and maintained by the LNST upstream and later it will also import test classes
based on user configured directories (from lnst-ctl.conf).

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Tests.Ping import Ping
from lnst.Tests.PacketAssert import PacketAssert
from lnst.Tests.Iperf import IperfClient, IperfServer
from lnst.Tests.RDMABandwidth import RDMABandwidthClient, RDMABandwidthServer
from lnst.Tests.PktGen import PktGen
from lnst.Tests.XDPBench import XDPBench
#TODO add support for test classes from lnst-ctl.conf
