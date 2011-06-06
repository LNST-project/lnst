"""
This module defines pktgen test, Tx side

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import logging
import re
from Common.TestsCommon import TestGeneric
from Common.ExecCmd import exec_cmd, ExecCmdFail

class Pktgen:
    def __init__(self, dev):
        self._dev = dev

    def set(self, val):
        exec_cmd("echo \"%s\" > %s" % (val, self._dev))

class TestPktgenTx(TestGeneric):
    def run(self):
        dev_name = self.get_mopt("netdev_name")
        addr = self.get_mopt("addr", opt_type="addr")
        hwaddr = self.get_mopt("hwaddr")
        vlan_tci = self.get_opt("vlan_tci", default=0)

        exec_cmd("modprobe pktgen")

        pgctl = Pktgen("/proc/net/pktgen/pgctrl")
        pgwrkr = Pktgen("/proc/net/pktgen/kpktgend_0")
        pg = Pktgen("/proc/net/pktgen/%s" % dev_name)

        try:
            pgwrkr.set("rem_device_all")
            pgwrkr.set("add_device %s" % dev_name)
            pgwrkr.set("max_before_softirq 5000")
            pg.set("clone_skb 100000")
            pg.set("pkt_size 60")
            pg.set("dst %s" % addr)
            pg.set("dst_mac %s" % hwaddr)
            if vlan_tci:
                pg.set("vlan_id %d" % vlan_tci)
            pg.set("count 10000000")
            pgctl.set("start")
        except ExecCmdFail:
            return self.set_fail("pktgen failed")

        return self.set_pass()
