import time
import signal
from lnst.Common.IpAddress import ipaddress
from lnst.Controller.Recipe import RecipeError
from lnst.Controller.RecipeResults import ResultLevel
from lnst.RecipeCommon.Perf import PerfConf, PerfMeasurementTool
from lnst.RecipeCommon.PerfResult import PerfInterval, StreamPerf
from lnst.RecipeCommon.PerfResult import MultiStreamPerf
from lnst.Tests.Iperf import IperfClient, IperfServer

class IperfMeasurementTool(PerfMeasurementTool):
    @staticmethod
    def perf_measure(perf_conf):
        _iperf_duration_overhead = 5

        server_params = dict(bind = ipaddress(perf_conf.server_bind),
                             oneoff = True)

        client_params = dict(server = server_params["bind"],
                             duration = perf_conf.duration,
                             parallel = perf_conf.streams)

        if perf_conf.test_type == "tcp_stream":
            #tcp stream is the default for iperf3
            pass
        elif perf_conf.test_type == "udp_stream":
            client_params["udp"] = True
        elif perf_conf.test_type == "sctp_stream":
            client_params["sctp"] = True
        else:
            raise RecipeError("Unsupported test type '{}'"
                              .format(perf_conf.test_type))

        server = IperfServer(**server_params)
        client = IperfClient(**client_params)

        server_host = perf_conf.server
        client_host = perf_conf.client
        result = None
        try:
            server_job = server_host.run(server, bg=True,
                                         job_level=ResultLevel.NORMAL)

            #wait for server to start, TODO can this be improved?
            time.sleep(2)

            duration = client.params.duration + _iperf_duration_overhead
            client_job = client_host.run(client, timeout=duration,
                                         job_level=ResultLevel.NORMAL)

            server_job.wait(timeout=5)
        finally:
            if client_job and not client_job.finished:
                client_job.kill()

            if server_job and not server_job.finished:
                server_job.kill()

        #TODO return something if not passed
        if client_job.passed:
            client_result = MultiStreamPerf()
            for i in client_job.result["data"]["end"]["streams"]:
                client_result.append(StreamPerf())

            for interval in client_job.result["data"]["intervals"]:
                for i, stream in enumerate(interval["streams"]):
                    client_result[i].append(PerfInterval(stream["bytes"] * 8,
                                                         stream["seconds"],
                                                         "bits"))

        #TODO return something if not passed
        if server_job.passed:
            server_result = MultiStreamPerf()
            for i in server_job.result["data"]["end"]["streams"]:
                server_result.append(StreamPerf())

            for interval in server_job.result["data"]["intervals"]:
                for i, stream in enumerate(interval["streams"]):
                    server_result[i].append(PerfInterval(stream["bytes"] * 8,
                                                         stream["seconds"],
                                                         "bits"))

        return client_result, server_result
