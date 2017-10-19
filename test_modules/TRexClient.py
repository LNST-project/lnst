"""
T-Rex client test module
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import os
import sys
import logging
from time import sleep
from lnst.Common.TestsCommon import TestGeneric

class TRexClient(TestGeneric):
    trex_stl_path = 'automation/trex_control_plane/stl'

    def __init__(self, command):
        super(TRexClient, self).__init__(command)

        self._trex_path = self.get_mopt("trex_path")
        self._ports = map(int, self.get_multi_mopt("ports"))

        self._src_macs = []
        self._dst_macs = []
        for port in self._ports:
            src_mac_name = "port%d_src_mac" % port
            dst_mac_name = "port%d_dst_mac" % port
            self._src_macs.append(self.get_mopt(src_mac_name))
            self._dst_macs.append(self.get_mopt(dst_mac_name))

        self._duration = int(self.get_mopt("duration"))
        self._runs = int(self.get_mopt("runs"))

        self._server_hostname = self.get_opt("server_hostname", default="localhost")
        self._pkt_size = self.get_opt("pkt_size", default=64)

        self._run_wait = int(self.get_opt("run_wait", default=5))

    def _postprocess_results(self, results):
        new_results = []
        for res in results:
            new_results.append({})
            new_res = new_results[-1]
            for key, data in res.items():
                if key in self._ports:
                    new_res["port_"+str(key)] = data
                else:
                    new_res[key] = data
        return new_results

    def run(self):
        sys.path.insert(0, os.path.join(self._trex_path, self.trex_stl_path))

        import trex_stl_lib.api as trex_api
        client = trex_api.STLClient(server=self._server_hostname)
        client.connect()

        try:
            client.acquire(ports=self._ports, force=True)
        except:
            res_data = {}
            res_data["msg"] = "Failed to acquire ports"
            return self.set_fail(res_data)

        try:
            client.reset(ports=self._ports)
        except:
            client.release(ports=self._ports)
            res_data = {}
            res_data["msg"] = "Failed to reset ports"
            return self.set_fail(res_data)

        for i, port in enumerate(self._ports):
            L2 = trex_api.Ether(src=self._src_macs[i], dst=self._dst_macs[i])
            L3 = trex_api.IP(src="192.168.1.%d" % (i*2+1),
                             dst="192.168.1.%d" % (i*2+2))
            L4 = trex_api.UDP()
            base_pkt = L2/L3/L4

            pad = max(0, self._pkt_size - len(base_pkt)) * 'x'
            packet = base_pkt/pad

            trex_packet = trex_api.STLPktBuilder(pkt=packet)

            trex_stream = trex_api.STLStream(packet=trex_packet,
                                             mode=trex_api.STLTXCont(percentage=100))

            client.add_streams(trex_stream, ports=[port])

        client.set_port_attr(ports=self._ports, promiscuous=True)

        results = []
        for i in range(self._runs):
            client.clear_stats(ports=self._ports)
            client.start(ports=self._ports)

            sleep(self._duration)

            client.stop(ports=self._ports)
            results.append(client.get_stats(ports=self._ports))

            #wait before starting next run
            sleep(self._run_wait)

        client.release(ports=self._ports)

        results = self._postprocess_results(results)

        res_data = {"results": results}
        res_data["msg"] = ""
        return self.set_pass(res_data)
