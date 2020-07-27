from lnst.Controller.RecipeResults import ResultLevel
from lnst.Recipes.ENRT.PerfTestMixins import BasePerfTestTweakMixin
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import BaseFlowMeasurement

class SctpFirewallPerfTestMixin(BasePerfTestTweakMixin):

    def _get_flow_measurement_from_config(self, perf_config):
        flow_measurements = [ m for m in perf_config.measurements if isinstance(m, BaseFlowMeasurement) ]
        return flow_measurements[0]

    def apply_perf_test_tweak(self, perf_config):
        super().apply_perf_test_tweak(perf_config)

        flow_measurement = self._get_flow_measurement_from_config(perf_config)
        flow = flow_measurement.conf[0]
        if flow.type == "sctp_stream":
            for nic in [flow.generator_nic, flow.receiver_nic]:
                nic.netns.run(
                    "iptables -I OUTPUT ! -o %s -p sctp -j DROP" % nic.name,
                    job_level=ResultLevel.NORMAL,
                )

    def remove_perf_test_tweak(self, perf_config):
        flow_measurement = self._get_flow_measurement_from_config(perf_config)
        flow = flow_measurement.conf[0]
        if flow.type == "sctp_stream":
            for nic in [flow.generator_nic, flow.receiver_nic]:
                nic.netns.run(
                    "iptables -D OUTPUT ! -o %s -p sctp -j DROP" % nic.name,
                    job_level=ResultLevel.NORMAL,
                )

        super().remove_perf_test_tweak(perf_config)
