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
import os
from Common.TestsCommon import TestGeneric
from Common.ExecCmd import exec_cmd, ExecCmdFail

class Pktgen:
    def __init__(self, dev):
        self._dev = dev

    def set(self, val):
        exec_cmd("echo \"%s\" > %s" % (val, self._dev))

class PktgenWorkers:
    def __init__(self):
        self._current = 0
        self._cpunum = int(os.sysconf('SC_NPROCESSORS_ONLN'))
        self._wrkrs = {}

    def _init_current_wrkr(self):
        num = self._current
        wrkr = Pktgen("/proc/net/pktgen/kpktgend_%d" % (num))
        wrkr.set("rem_device_all")
        wrkr.set("max_before_softirq 5000")
        self._wrkrs[num] = wrkr

    def _get_wrkr(self):
        num = self._current
        if not num in self._wrkrs:
            self._init_current_wrkr()
        wrkr = self._wrkrs[num]
        num += 1
        if num == self._cpunum:
            num = 0
        self._current = num
        return wrkr

    def add_device(self, dev_name):
        wrkr = self._get_wrkr()
        wrkr.set("add_device %s" % dev_name)

class TestPktgenTx(TestGeneric):
    def run(self):
        dev_names = self.get_multi_mopt("netdev_name")
        addr = self.get_mopt("addr", opt_type="addr")
        hwaddr = self.get_mopt("hwaddr")
        vlan_tci = self.get_opt("vlan_tci", default=0)
        skb_clone = self.get_opt("skb_clone", default=100000)
        count = self.get_opt("count", default=10000000)

        exec_cmd("modprobe pktgen")

        pgctl = Pktgen("/proc/net/pktgen/pgctrl")
        pgwrkr = PktgenWorkers()

        try:
            for dev_name in dev_names:
                pgwrkr.add_device(dev_name)
                pg = Pktgen("/proc/net/pktgen/%s" % dev_name)
                pg.set("clone_skb %s" % skb_clone)
                pg.set("pkt_size 60")
                pg.set("dst %s" % addr)
                pg.set("dst_mac %s" % hwaddr)
                if vlan_tci:
                    pg.set("vlan_id %d" % vlan_tci)
                pg.set("count %d" % count)
            pgctl.set("start")
        except ExecCmdFail:
            return self.set_fail("pktgen failed")

        return self.set_pass()
