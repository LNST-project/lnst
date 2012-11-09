__author__ = """
jpirko@redhat.com (Jiri Pirko)
jmalanik@redhat.com (Jan Malanik)
jtluka@redhat.com (Jan Tluka)
"""


import logging
import re
from lnst.Common.TestsCommon import TestGeneric
from lnst.Common.ExecCmd import exec_cmd


class TestIcmp6Ping(TestGeneric):
    def compose_cmd(self):
        addr = self.get_mopt("addr", opt_type="addr")
        cmd = "ping6 %s" % addr

        iface = self.get_opt("iface")
        if iface:
            cmd += " -I %s" % iface

        count = self.get_opt("count")
        if count:
            cmd += " -c %s" % count

        interval = self.get_opt("interval")
        if interval:
            cmd += " -i %s" % interval

        return cmd

    def run(self):
        cmd = self.compose_cmd()
        logging.debug("%s" % cmd)

        limit_rate = self.get_opt("limit_rate ", default=80)
        data_stdout = exec_cmd(cmd, die_on_err=False)[0]

        stat_pttr1 = r'(\d+) packets transmitted, (\d+) received'
        stat_pttr2 = r' rtt min/avg/max/mdev = \
            (\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+) ms'

        match = re.search(stat_pttr1, data_stdout)
        if not match:
            return self.set_fail("expected pattern not found")

        trans_pkts, recv_pkts = match.groups()
        rate = int(round((float(recv_pkts) / float(trans_pkts)) * 100))
        logging.debug("Transmitted \"%s\", received \"%s\", " \
            "rate \"%d%%\", limit_rate \"%d%%\"" \
            % (trans_pkts, recv_pkts, rate, limit_rate ))

        match = re.search(stat_pttr2, data_stdout)
        if match:
            tmin, tavg, tmax, tmdev = [float(x) for x in match.groups()]
            logging .debug("rtt min \"%.3f\", avg \"%.3f\", max \"%.3f\", "
                  "mdev \"%.3f\"" % (tmin, tavg, tmax, tmdev))

        if rate < limit_rate :
            return self.set_fail("rate is lower that limit")

        return self.set_pass()
