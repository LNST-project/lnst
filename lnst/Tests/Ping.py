import re
import logging
import subprocess
from lnst.Common.Parameters import IntParam, FloatParam, HostnameOrIpParam, DeviceOrIpParam
from lnst.Common.Utils import is_installed
from lnst.Common.IpAddress import Ip6Address
from lnst.Tests.BaseTestModule import BaseTestModule

class Ping(BaseTestModule):
    """Port of old IcmpPing test modules"""
    dst = HostnameOrIpParam(mandatory=True)
    count = IntParam(default=10)
    interval = FloatParam(default=1.0)
    interface = DeviceOrIpParam(mandatory=False)
    size = IntParam()

    def _compose_cmd(self):
        cmd = "ping %s" % self.params.dst
        if isinstance(self.params.dst, Ip6Address):
            cmd += " -6"
        cmd += " -c %d" % self.params.count
        cmd += " -i %f" % self.params.interval
        if "interface" in self.params:
            from lnst.Devices.Device import Device
            if isinstance(self.params.interface, Device):
                cmd += " -I %s" % self.params.interface.name
            else:
                cmd += " -I %s" % str(self.params.interface)

        if "size" in self.params:
            cmd += " -s %d" % self.params.size
        return cmd

    def run(self):
        self._res_data = {}
        if not is_installed("ping"):
            self._res_data["msg"] = "Ping is not installed on this machine!"
            logging.error(self._res_data["msg"])
            return False

        cmd = self._compose_cmd()

        logging.debug("compiled command: {}".format(cmd))

        ping_process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, close_fds=True)

        try:
            stdout, stderr = ping_process.communicate()
            stdout = stdout.decode()
            stderr = stderr.decode()
        except KeyboardInterrupt:
            pass

        if ping_process.returncode > 1:
            self._res_data["msg"] = "returncode = {}".format(ping_process.returncode)
            logging.error(self._res_data["msg"])
            if stderr != "":
                self._res_data["stderr"] = stderr
                logging.error("errors reported by ping")
                logging.error(self._res_data["stderr"])
            return False

        stat_pttr1 = r'(\d+) packets transmitted, (\d+) received'
        stat_pttr2 = r'rtt min/avg/max/mdev = (\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+) ms'

        match = re.search(stat_pttr1, stdout)
        if not match:
            self._res_data = {"msg": "expected pattern not found"}
            logging.error(self._res_data["msg"])
            return False
        else:
            trans_pkts, recv_pkts = match.groups()
            rate = int(round((float(recv_pkts) / float(trans_pkts)) * 100))
            logging.debug("Transmitted '{}', received '{}', "
                          "rate '{}%'".format(trans_pkts, recv_pkts, rate))

            self._res_data = {"trans_pkts": trans_pkts,
                              "recv_pkts": recv_pkts,
                              "rate": rate}

        match = re.search(stat_pttr2, stdout)
        if not match:
            if self._res_data['rate'] > 0:
                self._res_data = {"msg": "expected pattern not found"}
                logging.error(self._res_data["msg"])
                return False
        else:
            tmin, tavg, tmax, tmdev = [float(x) for x in match.groups()]
            logging.debug("rtt min \"%.3f\", avg \"%.3f\", max \"%.3f\", "
                          "mdev \"%.3f\"" % (tmin, tavg, tmax, tmdev))

            self._res_data["rtt_min"] = tmin
            self._res_data["rtt_max"] = tmax
            self._res_data["rtt_avg"] = tavg
            self._res_data["rtt_mdev"] = tmdev

        return True
