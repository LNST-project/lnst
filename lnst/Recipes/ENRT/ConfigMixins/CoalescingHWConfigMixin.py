from lnst.Common.Parameters import BoolParam

from lnst.Recipes.ENRT.ConfigMixins.BaseHWConfigMixin import BaseHWConfigMixin


class CoalescingHWConfigMixin(BaseHWConfigMixin):
    """
    This class is an extension to the :any:`BaseEnrtRecipe` class that enables
    adaptive coalescing configuration on the devices defined by
    :attr:`coalescing_hw_config_dev_list` property.

    :param adaptive_tx_coalescing:
        (optional test parameter) boolean to enable/disable TX adaptive
        coalescing on the devices
    :param adaptive_rx_coalescing:
        (optional test parameter) boolean to enable/disable RX adaptive
        coalescing on the devices
    """

    adaptive_rx_coalescing = BoolParam(mandatory=False)
    adaptive_tx_coalescing = BoolParam(mandatory=False)

    @property
    def coalescing_hw_config_dev_list(self):
        """
        The value of this property is a list of devices for which the
        adaptive coalescing features should be configured. It has to be
        defined by a derived class.
        """
        return []

    def hw_config(self, config):
        super().hw_config(config)

        self._configure_dev_attribute(
            config,
            self.coalescing_hw_config_dev_list,
            "adaptive_rx_coalescing",
            getattr(self.params, "adaptive_rx_coalescing", None),
        )
        self._configure_dev_attribute(
            config,
            self.coalescing_hw_config_dev_list,
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
