import signal
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
    started_job = None

    def packet_assert_test_start(self, packet_assert_config):
        if self.started_job:
            raise LnstError("Only 1 packet_assert job is allowed to run at a time.")

        host = packet_assert_config.host
        kwargs = self._generate_packet_assert_kwargs(packet_assert_config)
        packet_assert = PacketAssert(**kwargs)
        self.started_job = host.prepare_job(packet_assert).start(bg=True)

    def packet_assert_test_stop(self):
        if not self.started_job:
            raise LnstError("No packet_assert job is running.")

        self.started_job.kill(signal=signal.SIGINT)
        self.started_job.wait()
        if not self.started_job.passed:
            result = {}
        else:
            result = self.started_job.result
        self.started_job = None
        return result

    def packet_assert_evaluate_and_report(self, packet_assert_config, results):
        if not results:
            self.add_result(False, "Packet assert results unavailable")
            return

        success = False
        if results["p_recv"] >= packet_assert_config.p_min and \
            (results["p_recv"] <= packet_assert_config.p_max or
             not packet_assert_config.p_max):
            success = True

        cmp_msg = "packets received {}, expected min({}) max({})".format(
            results["p_recv"],
            packet_assert_config.p_min,
            packet_assert_config.p_max
        )
        self.add_result(
            success,
            "Packet assert {}, {}".format(
                "successful" if success else "unsuccessful",
                cmp_msg
            ),
            results
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
