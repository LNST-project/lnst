"""
This module defines icmp ping test

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import logging
import re
from lnst.Common.TestsCommon import TestGeneric
from lnst.Common.ExecCmd import exec_cmd

class IcmpPing(TestGeneric):
    def _compose_cmd(self):
        addr = self.get_mopt("addr", opt_type="addr")
        cmd = "ping %s" % addr
        count = self.get_opt("count")
        if count:
            cmd += " -c %s" % count
        interval = self.get_opt("interval")
        if interval:
            cmd += " -i %s" % interval
        iface = self.get_opt("iface")
        if iface:
            cmd += " -I %s" % iface
        size = self.get_opt("size")
        if size:
            cmd += " -s %s" % size
        return cmd

    def run(self):
        cmd = self._compose_cmd()
        limit_rate = self.get_opt("limit_rate", default=80)

        data_stdout = exec_cmd(cmd, die_on_err=False)[0]
        stat_pttr1 = r'(\d+) packets transmitted, (\d+) received'
        stat_pttr2 = r'rtt min/avg/max/mdev = (\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+) ms'

        match = re.search(stat_pttr1, data_stdout)
        if not match:
            res_data = {"msg": "expected pattern not found"}
            return self.set_fail(res_data)

        trans_pkts, recv_pkts = match.groups()
        rate = int(round((float(recv_pkts) / float(trans_pkts)) * 100))
        logging.debug("Transmitted \"%s\", received \"%s\", "
                  "rate \"%d%%\", limit_rate \"%d%%\""
                                % (trans_pkts, recv_pkts, rate, limit_rate))

        res_data = {"rate": rate,
                    "limit_rate": limit_rate}

        match = re.search(stat_pttr2, data_stdout)
        if match:
            tmin, tavg, tmax, tmdev = [float(x) for x in match.groups()]
            logging.debug("rtt min \"%.3f\", avg \"%.3f\", max \"%.3f\", "
                      "mdev \"%.3f\"" % (tmin, tavg, tmax, tmdev))

            res_data["rtt_min"] = tmin
            res_data["rtt_max"] = tmax

        if rate < limit_rate:
            res_data["msg"] = "rate is lower than limit"
            return self.set_fail(res_data)

        return self.set_pass(res_data)
