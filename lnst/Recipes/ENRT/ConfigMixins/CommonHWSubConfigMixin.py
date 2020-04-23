from lnst.Recipes.ENRT.ConfigMixins.ParallelStreamQDiscHWConfigMixin import (
    ParallelStreamQDiscHWConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.DevInterruptHWConfigMixin import (
    DevInterruptHWConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.CoalescingHWConfigMixin import (
    CoalescingHWConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.MTUHWConfigMixin import MTUHWConfigMixin
from lnst.Recipes.ENRT.ConfigMixins.DisablePauseFramesHWConfigMixin import (
    DisablePauseFramesHWConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.BaseSubConfigMixin import BaseSubConfigMixin


class CommonHWSubConfigMixin(
    DisablePauseFramesHWConfigMixin,
    ParallelStreamQDiscHWConfigMixin,
    DevInterruptHWConfigMixin,
    CoalescingHWConfigMixin,
    MTUHWConfigMixin,
    BaseSubConfigMixin,
):
    """
    This class groups few related :any:`BaseSubConfigMixin` s for user's
    convenience. For more details, see the documentation of the individual
    ancestor classes.
    """

    def apply_sub_configuration(self, config):
        super().apply_sub_configuration(config)
        self.hw_config(config)

    def remove_sub_configuration(self, config):
        self.hw_deconfig(config)
        return super().remove_sub_configuration(config)

    def generate_sub_configuration_description(self, config):
        desc = super().generate_sub_configuration_description(config)
        desc.extend(self.describe_hw_config(config))
        return desc
