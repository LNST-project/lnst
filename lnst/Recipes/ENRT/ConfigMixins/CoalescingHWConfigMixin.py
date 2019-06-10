from lnst.Common.Parameters import BoolParam

from lnst.Recipes.ENRT.ConfigMixins.BaseHWConfigMixin import BaseHWConfigMixin


class CoalescingHWConfigMixin(BaseHWConfigMixin):
    adaptive_rx_coalescing = BoolParam(mandatory=False)
    adaptive_tx_coalescing = BoolParam(mandatory=False)

    def hw_config(self, config):
        super().hw_config(config)

        self._configure_dev_attribute(
            config,
            "adaptive_rx_coalescing",
            getattr(self.params, "adaptive_rx_coalescing", None),
        )
        self._configure_dev_attribute(
            config,
            "adaptive_tx_coalescing",
            getattr(self.params, "adaptive_tx_coalescing", None),
        )

    def describe_hw_config(self, config):
        desc = super().describe_hw_config(config)
        desc.extend(
            self._describe_dev_attribute(config, "adaptive_rx_coalescing")
        )
        desc.extend(
            self._describe_dev_attribute(config, "adaptive_tx_coalescing")
        )
        return desc
