import time
import signal
import logging
from lnst.Common.IpAddress import ipaddress
from lnst.Controller.Recipe import RecipeError
from lnst.Controller.RecipeResults import ResultLevel
from lnst.RecipeCommon.Perf import PerfConf, PerfMeasurementTool
from lnst.RecipeCommon.PerfResult import PerfInterval, StreamPerf
from lnst.RecipeCommon.PerfResult import MultiStreamPerf

from lnst.Tests.TRex import TRexServer, TRexClient

class TRexMeasurementTool(PerfMeasurementTool):
    def __init__(self, trex_dir):
        self._trex_dir = trex_dir

    def perf_measure(self, perf_conf):
        generator = perf_conf.generator

        flows = []
        for src, dst in zip(perf_conf.generator_bind, perf_conf.receiver_bind):
            flows.append((
                dict(mac_addr=src.hwaddr,
                     pci_addr=src.bus_info,
                     ip_addr=src.ips[0]),
                dict(mac_addr=dst.hwaddr,
                     pci_addr=dst.bus_info,
                     ip_addr=dst.ips[0])))

        try:
            server = generator.run(
                    TRexServer(
                        trex_dir=self._trex_dir,
                        flows=flows,
                        cores=["2", "3", "4"]),
                    bg=True)

            #wait for server to start up
            #TODO better options??
            time.sleep(5)

            test = TRexClient(
                    trex_dir=self._trex_dir,
                    ports=range(len(flows)),
                    flows=flows,
                    duration=perf_conf.duration,
                    msg_size=perf_conf.msg_size)
            client = generator.run(
                    test,
                    timeout=test.runtime_estimate())
        finally:
            server.kill(signal.SIGINT)
            if not server.wait(5):
                server.kill(signal.SIGKILL)

        client_result = None
        if client.passed:
            tx_result = MultiStreamPerf()
            rx_result = MultiStreamPerf()
            for port in range(len(flows)):
                tx_stream = StreamPerf()
                rx_stream = StreamPerf()

                prev_time = client.result["start_time"]
                prev_tx_val = 0
                prev_rx_val = 0
                for i in client.result["data"]:
                    time_delta = i["timestamp"] - prev_time
                    tx_delta = i["measurement"][port]["opackets"] - prev_tx_val
                    rx_delta = i["measurement"][port]["ipackets"] - prev_rx_val 
                    tx_stream.append(PerfInterval(
                                tx_delta,
                                time_delta,
                                "pkts"))
                    rx_stream.append(PerfInterval(
                                rx_delta,
                                time_delta,
                                "pkts"))

                    prev_time = i["timestamp"]
                    prev_tx_val = i["measurement"][port]["opackets"]
                    prev_rx_val = i["measurement"][port]["ipackets"]

                tx_result.append(tx_stream)
                rx_result.append(rx_stream)

        return tx_result, rx_result
