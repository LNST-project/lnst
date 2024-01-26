from dataclasses import dataclass, field
from collections.abc import Sequence
from typing import Optional

from lnst.Common.IpAddress import BaseIpAddress
from lnst.Controller.Namespace import Namespace
from lnst.Controller.Recipe import BaseRecipe
from lnst.Controller.RecipeResults import MeasurementResult
from lnst.RecipeCommon.BaseResultEvaluator import BaseResultEvaluator
from lnst.Tests import Ping


@dataclass(eq=False)
class PingConf:
    client: Namespace
    client_bind: BaseIpAddress
    destination: Namespace
    destination_address: BaseIpAddress
    count: Optional[int] = None
    interval: Optional[int] = None
    size: Optional[int] = None
    evaluators: Sequence[BaseResultEvaluator] = field(default_factory=list)


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
        self.add_custom_result(MeasurementResult("ping", result[0], message, result[1]))

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
