import re
import logging
from lnst.Common.Parameters import IntParam, FloatParam, IpParam, DeviceParam
from lnst.Common.TestModule import BaseTestModule, TestModuleError
from lnst.Common.ExecCmd import exec_cmd

class IcmpPing(BaseTestModule):
    """Port of old IcmpPing test modules"""
    dst = IpParam(mandatory=True)
    count = IntParam(default=10)
    interval = FloatParam(default=1.0)
    iface = DeviceParam()
    size = IntParam()
    limit_rate = IntParam(default=80)

    def _compose_cmd(self):
        cmd = "ping %s" % self.params.dst
        cmd += " -c %d" % self.params.count
        cmd += " -i %f" % self.params.interval
        if "iface" in self.params:
           cmd += " -I %s" % self.params.iface.name

        if "size" in self.params:
            cmd += " -s %d" % self.params.size
        return cmd

    def run(self):
        cmd = self._compose_cmd()

        limit_rate = self.params.limit_rate

        data_stdout = exec_cmd(cmd, die_on_err=False)[0]
        stat_pttr1 = r'(\d+) packets transmitted, (\d+) received'
        stat_pttr2 = r'rtt min/avg/max/mdev = (\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+) ms'

        match = re.search(stat_pttr1, data_stdout)
        if not match:
            self._res_data = {"msg": "expected pattern not found"}
            return False

        trans_pkts, recv_pkts = match.groups()
        rate = int(round((float(recv_pkts) / float(trans_pkts)) * 100))
        logging.debug("Transmitted \"%s\", received \"%s\", "
                      "rate \"%d%%\", limit_rate \"%d%%\""
                      % (trans_pkts, recv_pkts, rate, limit_rate))

        self._res_data = {"rate": rate,
                          "limit_rate": limit_rate}

        match = re.search(stat_pttr2, data_stdout)
        if match:
            tmin, tavg, tmax, tmdev = [float(x) for x in match.groups()]
            logging.debug("rtt min \"%.3f\", avg \"%.3f\", max \"%.3f\", "
                          "mdev \"%.3f\"" % (tmin, tavg, tmax, tmdev))

            self._res_data["rtt_min"] = tmin
            self._res_data["rtt_max"] = tmax

        if rate < limit_rate:
            self._res_data["msg"] = "rate is lower than limit"
            return False

        return True
