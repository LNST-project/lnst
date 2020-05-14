from time import sleep
from lnst.Common.Parameters import BoolParam
from lnst.Recipes.ENRT.ConfigMixins.BaseHWConfigMixin import BaseHWConfigMixin


class PauseFramesHWConfigMixin(BaseHWConfigMixin):
    """
    This class is an extension to the :any:`BaseEnrtRecipe` class to configure
    the Ethernet pause frames on the devices defined by
    the :attr:`pause_frames_dev_list` property.
    """

    rx_pause_frames = BoolParam(mandatory=False)
    tx_pause_frames = BoolParam(mandatory=False)

    @property
    def pause_frames_dev_list(self):
        """
        The value of this property is a list of devices for which the pause
        frames should be configured. It has to be defined by a derived class.
        """
        return []

    def hw_config(self, config):
        super().hw_config(config)

        for param in ["rx_pause_frames", "tx_pause_frames"]:
            param_value = getattr(self.params, param, None)
            if param_value is not None:
                self._configure_dev_attribute(
                    config,
                    self.pause_frames_dev_list,
                    param,
                    param_value
                )

    def hw_deconfig(self, config):
        for param in ["rx_pause_frames", "tx_pause_frames"]:
            self._deconfigure_dev_attribute(
                config,
                self.pause_frames_dev_list,
                param
            )

        super().hw_deconfig(config)

    def describe_hw_config(self, config):
        desc = super().describe_hw_config(config)
        for param in ["rx_pause_frames", "tx_pause_frames"]:
            desc.extend(
                    self._describe_dev_attribute(config, param)
                    )

        return desc
