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


class CommonHWConfigMixin(
    ParallelStreamQDiscHWConfigMixin,
    DevInterruptHWConfigMixin,
    CoalescingHWConfigMixin,
    MTUHWConfigMixin,
):
    def test_wide_configuration(self):
        configuration = super().test_wide_configuration()
        self.hw_config(configuration)
        return configuration

    def test_wide_deconfiguration(self, configuration):
        self.hw_deconfig(configuration)
        return super().test_wide_deconfiguration(configuration)

    def generate_test_wide_description(self, config):
        desc = super().generate_test_wide_description(config)
        desc.extend(self.describe_hw_config(config))
        return desc
