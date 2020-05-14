from time import sleep
from lnst.Recipes.ENRT.ConfigMixins.BaseHWConfigMixin import BaseHWConfigMixin


class PauseFramesHWConfigMixin(BaseHWConfigMixin):
    """
    This class is an extension to the :any:`BaseEnrtRecipe` class to turn off
    the Ethernet pause frames on the devices defined by
    the :attr:`no_pause_frames_dev_list` property.
    """

    @property
    def no_pause_frames_dev_list(self):
        """
        The value of this property is a list of devices for which the pause
        frames should be disabled. It has to be defined by a derived class.
        """
        return []

    def hw_config(self, config):
        super().hw_config(config)

        for dev in self.no_pause_frames_dev_list:
            dev.host.run("ethtool -A {} rx off tx off".format(dev.name))
            sleep(1)
            dev.host.run("ethtool -a {}".format(dev.name))

    def hw_deconfig(self, config):
        for dev in self.no_pause_frames_dev_list:
            dev.host.run("ethtool -A {} rx on tx on".format(dev.name))

        super().hw_deconfig(config)

    def describe_hw_config(self, config):
        desc = super().describe_hw_config(config)
        desc += [
            "Pause frames disabled for: {}".format(
                self.no_pause_frames_dev_list
            )
        ]
        return desc
