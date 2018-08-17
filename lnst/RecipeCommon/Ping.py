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

class PingTestAndEvaluate(BaseRecipe):
    def ping_test(self, ping_config):
        client = ping_config.client
        destination = ping_config.destination

        ping = Ping(self._generate_ping_kwargs(ping_config))

        ping_job = client.run(ping)
        return ping_job.result

    def ping_evaluate_and_report(self, ping_config, results):
        # do we want to use the "perf" measurements (store a baseline etc...) as well?
        if results["rate"] > 50:
            self.add_result(True, "Ping succesful", results)
        else:
            self.add_result(False, "Ping unsuccesful", results)

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
