from lnst.Controller.Recipe import BaseRecipe
from lnst.RecipeCommon.PerfResult import MultiRunPerf

class PerfConf(object):
    def __init__(self,
                 perf_tool,
                 client, client_bind,
                 server, server_bind,
                 test_type,
                 msg_size, duration, iterations, streams):
        self._perf_tool = perf_tool
        self._client = client
        self._client_bind = client_bind
        self._server = server
        self._server_bind = server_bind

        self._test_type = test_type

        self._msg_size = msg_size
        self._duration = duration
        self._iterations = iterations
        self._streams = streams

    @property
    def perf_tool(self):
        return self._perf_tool

    @property
    def client(self):
        return self._client

    @property
    def client_bind(self):
        return self._client_bind

    @property
    def server(self):
        return self._server

    @property
    def server_bind(self):
        return self._server_bind

    @property
    def test_type(self):
        return self._test_type

    @property
    def msg_size(self):
        return self._msg_size

    @property
    def duration(self):
        return self._duration

    @property
    def iterations(self):
        return self._iterations

    @property
    def streams(self):
        return self._streams

class PerfMeasurementTool(object):
    @staticmethod
    def perf_measure(perf_conf):
        raise NotImplementedError

class PerfTestAndEvaluate(BaseRecipe):
    def perf_test(self, perf_conf):
        client_measurements = MultiRunPerf()
        server_measurements = MultiRunPerf()
        for i in range(perf_conf.iterations):
            client, server = perf_conf.perf_tool.perf_measure(perf_conf)

            client_measurements.append(client)
            server_measurements.append(server)

        return client_measurements, server_measurements

    def perf_evaluate_and_report(self, perf_conf, results, baseline):
        self.perf_evaluate(perf_conf, results, baseline)

        self.perf_report(perf_conf, results, baseline)

    def perf_evaluate(self, perf_conf, results, baseline):
        client, server = results

        if client.average > 0:
            self.add_result(True, "Client reported non-zero throughput")
        else:
            self.add_result(False, "Client reported zero throughput")

        if server.average > 0:
            self.add_result(True, "Server reported non-zero throughput")
        else:
            self.add_result(False, "Server reported zero throughput")


    def perf_report(self, perf_conf, results, baseline):
        client, server = results

        self.add_result(True,
                        "Client measured throughput: {tput} +-{deviation} {unit} per second"
                            .format(tput=client.average,
                                    deviation=client.std_deviation,
                                    unit=client.unit),
                        data = client)
        self.add_result(True,
                        "Server measured throughput: {tput} +-{deviation} {unit} per second"
                            .format(tput=server.average,
                                    deviation=server.std_deviation,
                                    unit=server.unit),
                        data = server)
