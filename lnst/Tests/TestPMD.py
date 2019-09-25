import logging
import subprocess
import signal
from lnst.Common.Parameters import Param, StrParam, IntParam, FloatParam
from lnst.Common.Parameters import IpParam, DeviceOrIpParam
from lnst.Tests.BaseTestModule import BaseTestModule, TestModuleError

class TestPMD(BaseTestModule):
    coremask = StrParam(mandatory=True)
    pmd_coremask = StrParam(mandatory=True)

    #TODO make ListParam
    nics = Param(mandatory=True)
    peer_macs = Param(mandatory=True)

    def format_command(self):
        testpmd_args = ["testpmd",
                "-c", self.params.coremask,
                "-n", "4", "--socket-mem", "1024,0"]
        for nic in self.params.nics:
            testpmd_args.extend(["-w", nic])

        testpmd_args.extend(["--", "-i", "--forward-mode", "mac",
                             "--coremask", self.params.pmd_coremask])

        for i, mac in enumerate(self.params.peer_macs):
            testpmd_args.extend(["--eth-peer", "{},{}".format(i, mac)])

        return " ".join(testpmd_args)


    def run(self):
        cmd = self.format_command()
        logging.debug("Running command \"{}\" as subprocess".format(cmd))
        process = subprocess.Popen(cmd, shell=True,
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   close_fds=True)

        process.stdin.write(str.encode("start tx_first\n"))

        self.wait_for_interrupt()

        process.stdin.write(str.encode("stop\n"))
        process.stdin.write(str.encode("quit\n"))

        out, err = process.communicate()
        self._res_data = {"stdout": out, "stderr": err}
        return True
