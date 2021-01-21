from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from lnst.Recipes.ENRT.PerfTestMixins import CommonPerfTestTweakMixin
from lnst.Recipes.ENRT.ConfigMixins.DisableTurboboostMixin import (
    DisableTurboboostMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.DisableIdleStatesMixin import (
    DisableIdleStatesMixin,
)

from lnst.Recipes.ENRT.MeasurementGenerators.IperfMeasurementGenerator import (
    IperfMeasurementGenerator,
)
from lnst.Recipes.ENRT.MeasurementGenerators.HypervisorsStatCPUMeasurementGenerator import (
    HypervisorsStatCPUMeasurementGenerator,
)


class VirtualEnrtRecipe(
    CommonPerfTestTweakMixin,
    DisableTurboboostMixin,
    DisableIdleStatesMixin,
    HypervisorsStatCPUMeasurementGenerator,
    IperfMeasurementGenerator,
    BaseEnrtRecipe,
):
    @property
    def hypervisor_hosts(self):
        return set([self.matched.host1, self.matched.host2])

    @property
    def disable_idlestates_host_list(self):
        """
        The `disable_idlestates_host_list` property value is the list of all
        matched baremetal hosts for the recipe.

        For detailed explanation of this property see
        :any:`DisableIdleStatesMixin` and
        :any:`DisableIdleStatesMixin.disable_idlestates_host_list`.
        """
        return self.hypervisor_hosts

    @property
    def disable_turboboost_host_list(self):
        """
        The `disable_turboboost_host_list` property value is the list of all
        matched baremetal hosts for the recipe.

        For detailed explanation of this property see
        :any:`DisableTurboboostMixin` and
        :any:`DisableTurboboostMixin.disable_turboboost_host_list`.
        """
        return self.hypervisor_hosts
