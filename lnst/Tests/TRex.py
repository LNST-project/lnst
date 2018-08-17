import os
import sys
import yaml
import time
import logging
import subprocess
import tempfile
import signal
from lnst.Common.Parameters import Param, StrParam, IntParam, FloatParam
from lnst.Common.Parameters import IpParam, DeviceOrIpParam
from lnst.Tests.BaseTestModule import BaseTestModule, TestModuleError

class TRexCommon(BaseTestModule):
    trex_dir = StrParam(mandatory=True)

class TRexClient(TRexCommon):
    #make Int List
    ports = Param(mandatory=True)

    flows = Param(mandatory=True)

    duration = IntParam(mandatory=True)
    warmup_time = IntParam(default=5)

    msg_size = IntParam(default=64)

    server_hostname = StrParam(default="localhost")
    trex_stl_path = 'trex_client/interactive'

    def runtime_estimate(self):
        _duration_overhead = 5
        return (self.params.duration +
                self.params.warmup_time +
                _duration_overhead)

    def run(self):
        sys.path.insert(0, os.path.join(self.params.trex_dir,
                                        self.trex_stl_path))

        from trex.stl import api as trex_api

        try:
            return self._run(trex_api)
        except trex_api.TRexError as e:
            #TRex errors aren't picklable so we wrap them like this
            raise TestModuleError(str(e))

    def _run(self, trex_api):
        client = trex_api.STLClient(server=self.params.server_hostname)
        client.connect()

        self._res_data = {}

        try:
            client.acquire(ports=self.params.ports, force=True)
        except:
            self._res_data["msg"] = "Failed to acquire ports"
            return False

        try:
            client.reset(ports=self.params.ports)
        except:
            client.release(ports=self.params.ports)
            self._res_data["msg"] = "Failed to reset ports"
            return False

        for i, (src, dst) in enumerate(self.params.flows):
            L2 = trex_api.Ether(
                    src=str(src["mac_addr"]),
                    dst=str(dst["mac_addr"]))
            L3 = trex_api.IP(
                    src=str(src["ip_addr"]),
                    dst=str(dst["ip_addr"]))
            L4 = trex_api.UDP()
            base_pkt = L2/L3/L4

            pad = max(0, self.params.msg_size - len(base_pkt)) * 'x'
            packet = base_pkt/pad

            trex_packet = trex_api.STLPktBuilder(pkt=packet)

            trex_stream = trex_api.STLStream(
                    packet=trex_packet,
                    mode=trex_api.STLTXCont(percentage=100))

            port = self.params.ports[i]
            client.add_streams(trex_stream, ports=[port])

        client.set_port_attr(ports=self.params.ports, promiscuous=True)


        measurements = []

        client.start(ports=self.params.ports)

        time.sleep(self.params.warmup_time)

        client.clear_stats(ports=self.params.ports)
        self._res_data["start_time"] = time.time()

        for i in range(self.params.duration):
            time.sleep(1)
            measurements.append(dict(timestamp=time.time(),
                                     measurement=client.get_stats(
                                         ports=self.params.ports,
                                         sync_now=True)))

        client.stop(ports=self.params.ports)
        client.release(ports=self.params.ports)

        self._res_data["data"] = measurements
        return True

class TRexServer(TRexCommon):
    #TODO make ListParam
    flows = Param(mandatory=True)

    cores = Param(mandatory=True)

    def run(self):
        trex_server_conf = [{'port_limit': len(self.params.flows),
                             'version': 2,
                             'interfaces': [],
                             'platform': {
                                 'dual_if': [{
                                     'socket': 0,
                                     'threads': self.params.cores}],
                                 'latency_thread_id': 0,
                                 'master_thread_id': 1},
                             'port_info': []}]

        for src, dst in self.params.flows:
            short_pci_addr = src["pci_addr"].partition(':')[2]
            trex_server_conf[0]['interfaces'].append(short_pci_addr)
            trex_server_conf[0]['port_info'].append(
                    {'src_mac': str(src["mac_addr"]),
                     'dest_mac': str(dst["mac_addr"])})

        with tempfile.NamedTemporaryFile() as cfg_file:
            yaml.dump(trex_server_conf, cfg_file)
            cfg_file.flush()
            os.fsync(cfg_file.file.fileno())

            os.chdir(self.params.trex_dir)
            server = subprocess.Popen(
                    [os.path.join(self.params.trex_dir, "t-rex-64"),
                        "--cfg", cfg_file.name, "-i"],
                    stdin=open('/dev/null'), stdout=open('/dev/null','w'),
                    stderr=subprocess.PIPE, close_fds=True)

            self.wait_for_interrupt()

            server.send_signal(signal.SIGINT)
            out, err = server.communicate()
            if err:
                logging.error(err)
                return False

        return True
