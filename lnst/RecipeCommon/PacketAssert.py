import signal

from lnst.Controller.RecipeResults import ResultType
from lnst.Controller.Recipe import BaseRecipe
from lnst.Tests import PacketAssert
from lnst.Common.LnstError import LnstError

class PacketAssertConf(object):
    def __init__(self, host, iface, **kwargs):
        self._host = host
        self._iface = iface
        self._p_filter = kwargs.get("p_filter", '')
        self._grep_for = kwargs.get("grep_for", [])
        self._p_min = kwargs.get("p_min", 10)
        self._p_max = kwargs.get("p_max", 0)
        self._promiscuous = kwargs.get("promiscuous", False)

    @property
    def host(self):
        return self._host

    @property
    def iface(self):
        return self._iface

    @property
    def p_filter(self):
        return self._p_filter

    @property
    def grep_for(self):
        return self._grep_for

    @property
    def p_min(self):
        return self._p_min

    @property
    def p_max(self):
        return self._p_max

    @property
    def promiscuous(self):
        return self._promiscuous

class PacketAssertTestAndEvaluate(BaseRecipe):
    packet_assert_jobs = []

    def packet_assert_test_start(self, packet_assert_configs):
        for packet_assert_config in packet_assert_configs:
            host = packet_assert_config.host
            kwargs = self._generate_packet_assert_kwargs(packet_assert_config)
            packet_assert = PacketAssert(**kwargs)
            self.packet_assert_jobs.append(host.prepare_job(packet_assert).start(bg=True))

    def packet_assert_test_stop(self):
        if not self.packet_assert_jobs:
            raise LnstError("No packet_assert job is running.")

        results = []
        for packet_assert_job in self.packet_assert_jobs:
            packet_assert_job.kill(signal=signal.SIGINT)
            packet_assert_job.wait()
            if not packet_assert_job.passed:
                results.append({})
            else:
                results.append(packet_assert_job.result)

        self.packet_assert_jobs = []

        return results

    def packet_assert_evaluate_and_report(self, packet_assert_configs, results):
        if not results:
            self.add_result(ResultType.FAIL, "Packet assert results unavailable")
            return

        for packet_assert_config, result in zip(packet_assert_configs, results):
            success = ResultType.FAIL
            if result["p_recv"] >= packet_assert_config.p_min and \
                (result["p_recv"] <= packet_assert_config.p_max or
                 not packet_assert_config.p_max):
                success = ResultType.PASS

            cmp_msg = "packets received {}, expected min({}) max({})".format(
                result["p_recv"],
                packet_assert_config.p_min,
                packet_assert_config.p_max
            )
            self.add_result(
                success,
                "Packet assert {}, {}".format(
                    "successful" if success else "unsuccessful",
                    cmp_msg
                ),
                result
            )

    def _generate_packet_assert_kwargs(self, packet_assert_config):
        kwargs = dict(interface=packet_assert_config.iface)

        if packet_assert_config.p_filter:
            kwargs["p_filter"] = packet_assert_config.p_filter

        if packet_assert_config.grep_for:
            kwargs["grep_for"] = packet_assert_config.grep_for

        if packet_assert_config.promiscuous:
            kwargs["promiscuous"] = packet_assert_config.promiscuous

        return kwargs
