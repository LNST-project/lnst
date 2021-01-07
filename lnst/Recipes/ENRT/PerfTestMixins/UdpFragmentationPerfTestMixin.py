from lnst.Common.LnstError import LnstError
from lnst.Common.Parameters import IntParam
from lnst.Common.IpAddress import ipaddress, AF_INET, AF_INET6
from lnst.Controller.RecipeResults import ResultLevel
from lnst.RecipeCommon.Perf.PerfTestMixins import BasePerfTestTweakMixin
from lnst.Recipes.ENRT.PerfTestMixins.Utils import (
    get_flow_measurements_from_config,
)


class UdpFragmentationPerfTestMixin(BasePerfTestTweakMixin):
    udp_fragmentation_threshold = IntParam(default=104857600)
    udp_fragmentation_time = IntParam(default=1)

    def apply_perf_test_tweak(self, perf_config):
        super().apply_perf_test_tweak(perf_config)

        flow_measurements = get_flow_measurements_from_config(perf_config)
        flow = flow_measurements[0].flows[0]
        tweak_config = perf_config.perf_test_tweak_config
        if flow.type == "udp_stream":
            tweak_config["udp_fragmentation"] = {}
            for host in self.matched:
                self._config_ip_fragmentation(tweak_config, host, flow)

    def _config_ip_fragmentation(self, config, host, flow):
        ip_version = self._flow_ip_version(flow)

        if ip_version == AF_INET:
            orig_thresh_value = host.run(
                "cat /proc/sys/net/ipv4/ipfrag_high_thresh",
                job_level=ResultLevel.DEBUG,
            )
            orig_time_value = host.run(
                "cat /proc/sys/net/ipv4/ipfrag_time",
                job_level=ResultLevel.DEBUG,
            )
            host.run(
                "echo {} > /proc/sys/net/ipv4/ipfrag_high_thresh".format(
                    self.params.udp_fragmentation_threshold
                ),
                job_level=ResultLevel.NORMAL,
            )
            host.run(
                "echo {} > /proc/sys/net/ipv4/ipfrag_time".format(
                    self.params.udp_fragmentation_time
                ),
                job_level=ResultLevel.NORMAL,
            )
        elif ip_version == AF_INET6:
            orig_thresh_value = host.run(
                "cat /proc/sys/net/ipv6/ip6frag_high_thresh",
                job_level=ResultLevel.DEBUG,
            )
            orig_time_value = host.run(
                "cat /proc/sys/net/ipv6/ip6frag_time",
                job_level=ResultLevel.DEBUG,
            )
            host.run(
                "echo {} > /proc/sys/net/ipv6/ip6frag_high_thresh".format(
                    self.params.udp_fragmentation_threshold
                ),
                job_level=ResultLevel.NORMAL,
            )
            host.run(
                "echo {} > /proc/sys/net/ipv6/ip6frag_time".format(
                    self.params.udp_fragmentation_time
                ),
                job_level=ResultLevel.NORMAL,
            )

        config["udp_fragmentation"][host] = {
            "ip_version": ip_version,
            "original_threshold": orig_thresh_value.stdout.strip(),
            "original_time": orig_time_value.stdout.strip(),
            "current_threshold": self.params.udp_fragmentation_threshold,
            "current_time": self.params.udp_fragmentation_time,
        }

    def remove_perf_test_tweak(self, perf_config):
        tweak_config = perf_config.perf_test_tweak_config
        if "udp_fragmentation" in tweak_config:
            for host, host_cfg in tweak_config["udp_fragmentation"].items():
                self._deconfig_ip_fragmentation(host_cfg, host)

            del tweak_config["udp_fragmentation"]

        super().remove_perf_test_tweak(perf_config)

    def _deconfig_ip_fragmentation(self, config, host):
        ip_version = config["ip_version"]

        if ip_version == AF_INET:
            host.run(
                "echo {} > /proc/sys/net/ipv4/ipfrag_high_thresh".format(
                    config["original_threshold"]
                ),
                job_level=ResultLevel.NORMAL,
            )
            host.run(
                "echo {} > /proc/sys/net/ipv4/ipfrag_time".format(
                    config["original_time"]
                ),
                job_level=ResultLevel.NORMAL,
            )
        elif ip_version == AF_INET6:
            host.run(
                "echo {} > /proc/sys/net/ipv6/ip6frag_high_thresh".format(
                    config["original_threshold"]
                ),
                job_level=ResultLevel.NORMAL,
            )
            host.run(
                "echo {} > /proc/sys/net/ipv6/ip6frag_time".format(
                    config["original_time"]
                ),
                job_level=ResultLevel.NORMAL,
            )
        else:
            raise LnstError("Unknown ip version: {}".format(ip_version))

    def generate_perf_test_tweak_description(self, perf_config):
        description = super().generate_perf_test_tweak_description(perf_config)
        tweak_config = perf_config.perf_test_tweak_config
        if "udp_fragmentation" in tweak_config:
            for host, host_cfg in tweak_config["udp_fragmentation"].items():
                description.append(
                    "Host {hid} configured ipfrag_high_thresh={value}, original={orig}".format(
                        hid=host.hostid,
                        value=host_cfg["current_threshold"],
                        orig=host_cfg["original_threshold"],
                    )
                )
                description.append(
                    "Host {hid} configured ipfrag_time={value}, original={orig}".format(
                        hid=host.hostid,
                        value=host_cfg["current_time"],
                        orig=host_cfg["original_time"],
                    )
                )
        else:
            description.append(
                "skipped configuration of fragmentation thresholds"
            )

        return description

    def _flow_ip_version(self, flow):
        return ipaddress(flow.generator_bind).family
