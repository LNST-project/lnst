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
from lnst.Common.TestsCommon import TestGeneric
from lnst.Common.ExecCmd import exec_cmd, ExecCmdFail

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

def pktget_options_merge(pktgen_options, default_pktgen_options):
    opts = [re.split('\s+', opt) for opt in pktgen_options]
    def_opts = [re.split('\s+', opt) for opt in default_pktgen_options]
    res = []
    for def_opt in def_opts:
        if not def_opt[0] in [opt[0] for opt in opts]:
            res.append(def_opt)
    res = res + opts
    return [" ".join(opt) for opt in res]

def pktgen_devices_remove():
    for cpu in range(os.sysconf('SC_NPROCESSORS_ONLN')):
        cmd = "echo rem_device_all > /proc/net/pktgen/kpktgend_{}"
        exec_cmd(cmd.format(cpu))

class PktgenTx(TestGeneric):
    def run(self):
        dev_names = self.get_multi_mopt("netdev_name")
        pktgen_options = self.get_multi_mopt("pktgen_option")
        thread_options = self.get_multi_opt("thread_option")

        default_pktgen_options = [
            "count 10000000",
            "clone_skb 100000",
            "pkt_size 60",
        ]
        pktgen_options = pktget_options_merge(pktgen_options,
                                              default_pktgen_options)

        exec_cmd("modprobe pktgen")

        pktgen_devices_remove()

        pgctl = Pktgen("/proc/net/pktgen/pgctrl")
        pgwrkr = PktgenWorkers()

        try:
            for idx, dev_name in enumerate(dev_names):
                pgwrkr.add_device(dev_name)
                pg = Pktgen("/proc/net/pktgen/%s" % dev_name)
                for pktgen_option in pktgen_options:
                    pg.set(pktgen_option)
                if not thread_options:
                    continue
                for thread_option in re.split(",", thread_options[idx]):
                    pg.set(thread_option)

            pgctl.set("start")
        except ExecCmdFail:
            res_data = {"msg": "pktgen failed"}
            return self.set_fail(res_data)

        return self.set_pass()
