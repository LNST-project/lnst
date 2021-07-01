from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from lnst.Recipes.ENRT.PerfTestMixins import CommonPerfTestTweakMixin
from lnst.Recipes.ENRT.ConfigMixins.DisableTurboboostMixin import (
    DisableTurboboostMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.DisableIdleStatesMixin import (
    DisableIdleStatesMixin,
)

from lnst.Recipes.ENRT.MeasurementGenerators.FlowMeasurementGenerator import (
    FlowMeasurementGenerator,
)
from lnst.Recipes.ENRT.MeasurementGenerators.FlowEndpointsStatCPUMeasurementGenerator import (
    FlowEndpointsStatCPUMeasurementGenerator,
)


class BaremetalEnrtRecipe(
    CommonPerfTestTweakMixin,
    DisableTurboboostMixin,
    DisableIdleStatesMixin,
    FlowEndpointsStatCPUMeasurementGenerator,
    FlowMeasurementGenerator,
    BaseEnrtRecipe,
):
    @property
    def disable_idlestates_host_list(self):
        """
        The `disable_idlestates_host_list` property value is the list of all
        matched baremetal hosts for the recipe.

        For detailed explanation of this property see
        :any:`DisableIdleStatesMixin` and
        :any:`DisableIdleStatesMixin.disable_idlestates_host_list`.
        """
        return self.matched

    @property
    def disable_turboboost_host_list(self):
        """
        The `disable_turboboost_host_list` property value is the list of all
        matched baremetal hosts for the recipe.

        For detailed explanation of this property see
        :any:`DisableTurboboostMixin` and
        :any:`DisableTurboboostMixin.disable_turboboost_host_list`.
        """
        return self.matched
