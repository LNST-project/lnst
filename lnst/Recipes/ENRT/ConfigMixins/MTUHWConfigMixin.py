from lnst.Common.Parameters import IntParam

from lnst.Recipes.ENRT.ConfigMixins.BaseHWConfigMixin import BaseHWConfigMixin


class MTUHWConfigMixin(BaseHWConfigMixin):
    mtu = IntParam(mandatory=False)

    def hw_config(self, config):
        super().hw_config(config)

        self._configure_dev_attribute(
            config, "mtu", getattr(self.params, "mtu", None)
        )

    def describe_hw_config(self, config):
        desc = super().describe_hw_config(config)
        return desc + self._describe_dev_attribute(config, "mtu")
