import re
import logging

from lnst.Recipes.ENRT.ConfigMixins.MultiDevInterruptHWConfigMixin import (
    MultiDevInterruptHWConfigMixin,
)
from lnst.Recipes.ENRT.MeasurementGenerators.XDPRedirectCPUMeasurementGenerator import (
    XDPRedirectCPUMeasurementGenerator,
)
from lnst.Recipes.ENRT.SimpleNetworkRecipe import SimpleNetworkRecipe
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration


class XDPRedirectCPURecipe(
    MultiDevInterruptHWConfigMixin,
    XDPRedirectCPUMeasurementGenerator,
    SimpleNetworkRecipe,
):
    """
    ENRT recipe measuring per-CPU packet throughput via ``xdp-bench
    redirect-cpu``.

    .. code-block:: none

        +--------+              +--------+
        | host1  |              | host2  |
        |  eth0 -+-- switch  ---+- eth0  |
        | pktgen |              | xdp-bench redirect-cpu |
        +--------+              +--------+

    host1 sends pktgen flows to host2. host2 runs ``xdp-bench redirect-cpu``
    with all target CPUs via ``-c`` flags using the ``round-robin`` program,
    which distributes packets evenly by packet count regardless of flow tuple.

    **host2 configuration applied before traffic:**

    - RSS hash key zeroed via ``ethtool -X`` so the NIC does not spread
      packets across hardware queues (all IRQs go to one CPU).
    - ``rxhash`` offload disabled.
    - NIC IRQs pinned to a single dedicated CPU via
      ``multi_dev_interrupt_config``. This CPU must not appear in
      ``perf_tool_cpu``.

    **Recommended parameter setup:**

    - ``perf_tool_cpu``: list of target CPUs on host2, e.g. ``[2, 4, 6]``
    - ``multi_dev_interrupt_config``: pin host2.eth0 IRQs to one CPU not in
      ``perf_tool_cpu``
    """

    def test_wide_configuration(self, config: EnrtConfiguration) -> EnrtConfiguration:
        config = super().test_wide_configuration(config)

        host2 = self.matched.host2
        dev = host2.eth0

        self._zero_rss_hash_key(host2, dev, config)
        host2.run(f"ethtool -K {dev.name} rxhash off")

        return config

    def test_wide_deconfiguration(self, config: EnrtConfiguration):
        host2 = self.matched.host2
        dev = host2.eth0

        self._restore_rss_hash_key(host2, dev, config)
        host2.run(f"ethtool -K {dev.name} rxhash on")

        super().test_wide_deconfiguration(config)
        return config

    def _zero_rss_hash_key(self, host, dev, config):
        result = host.run(f"ethtool -x {dev.name}")
        output = result.stdout

        key_match = re.search(r"RSS hash key:\s*\n((?:[0-9a-fA-F]{2}:?)+)", output)
        if key_match:
            original_key = key_match.group(1).strip()
            key_bytes = original_key.split(":")
            key_length = len(key_bytes)

            config.rss_original_hash_key = original_key

            zero_key = ":".join(["00"] * key_length)
            host.run(f"ethtool -X {dev.name} hkey {zero_key}")
            logging.info(
                f"Zeroed RSS hash key on {dev.name} (original length: {key_length} bytes)"
            )
        else:
            logging.warning(f"Could not parse RSS hash key from ethtool -x output")
            config.rss_original_hash_key = None

    def _restore_rss_hash_key(self, host, dev, config):
        original_key = getattr(config, "rss_original_hash_key", None)
        if original_key:
            host.run(f"ethtool -X {dev.name} hkey {original_key}")
            logging.info(f"Restored RSS hash key on {dev.name}")

    @property
    def offload_nics(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
