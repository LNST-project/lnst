from lnst.Common.Parameters import IntParam

from lnst.Recipes.ENRT.ConfigMixins.BaseHWConfigMixin import BaseHWConfigMixin


class MTUHWConfigMixin(BaseHWConfigMixin):
    """
    This class is an extension to the :any:`BaseEnrtRecipe` class that enables
    MTU configuration on the devices defined by the :attr:`mtu_hw_config_dev_list`
    property.

    :param mtu:
        (optional test parameter) MTU value to be configured on the devices
    """

    mtu = IntParam(mandatory=False)

    @property
    def mtu_hw_config_dev_list(self):
        """
        The value of this property is a list of devices for which the MTU
        should be configured. It has to be defined by a derived class.
        """
        return []

    def hw_config(self, config):
        super().hw_config(config)

        self._configure_dev_attribute(
            config, self.mtu_hw_config_dev_list, "mtu", getattr(self.params, "mtu", None)
        )

    def describe_hw_config(self, config):
        desc = super().describe_hw_config(config)
        return desc + self._describe_dev_attribute(config, "mtu")
