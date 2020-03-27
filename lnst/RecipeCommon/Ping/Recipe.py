from lnst.Controller.Recipe import BaseRecipe
from lnst.Tests import Ping

class PingConf(object):
    def __init__(self,
                 client, client_bind,
                 destination, destination_address,
                 count=None, interval=None, size=None):
        self._client = client
        self._client_bind = client_bind
        self._destination = destination
        self._destination_address = destination_address
        self._count = count
        self._interval = interval
        self._size = size
        self._evaluators = list()

    @property
    def client(self):
        return self._client

    @property
    def client_bind(self):
        return self._client_bind

    @property
    def destination(self):
        return self._destination

    @property
    def destination_address(self):
        return self._destination_address

    @property
    def count(self):
        return self._count

    @property
    def interval(self):
        return self._interval

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, value):
        self._size = value

    @property
    def evaluators(self):
        return self._evaluators

    def register_evaluators(self, evaluators):
        self._evaluators = list(evaluators)


class PingTestAndEvaluate(BaseRecipe):
    def ping_test(self, ping_configs):
        results = {}

        ping_array = []
        for pingconf in ping_configs:
            ping = self.ping_init(pingconf)
            ping.start(bg = True)
            ping_array.append((pingconf, ping))

        for _, pingjob in ping_array:
            try:
                pingjob.wait()
            finally:
                pingjob.kill()

        for pingconf, pingjob in ping_array:
            result = (pingjob.passed, pingjob.result)
            results[pingconf] = result

        return results

    def ping_init(self, ping_config):
        client = ping_config.client
        kwargs = self._generate_ping_kwargs(ping_config)
        ping = client.prepare_job(Ping(**kwargs))
        return ping

    def ping_report_and_evaluate(self, results):
        for pingconf, result in results.items():
            self.single_ping_report_and_evaluate(pingconf, result)

    def single_ping_report_and_evaluate(self, ping_config, result):
        self.single_ping_report(ping_config, result)

        self.single_ping_evaluate(ping_config, result)

    def single_ping_report(self, ping_config, result):
        fmt = "From: <{0.client.hostid} ({0.client_bind})> To: " \
              "<{0.destination.hostid} ({0.destination_address})>"
        description = fmt.format(ping_config)
        message = "Ping result --- " + description
        self.add_result(result[0], message, result[1])

    def single_ping_evaluate(self, ping_config, result):
        for evaluator in ping_config.evaluators:
            evaluator.evaluate_results(self, result[1])

    def _generate_ping_kwargs(self, ping_config):
        kwargs = dict(dst=ping_config.destination_address,
                      interface=ping_config.client_bind)

        if ping_config.count:
            kwargs["count"] = ping_config.count

        if ping_config.interval:
            kwargs["interval"] = ping_config.interval

        if ping_config.size:
            kwargs["size"] = ping_config.size
        return kwargs
