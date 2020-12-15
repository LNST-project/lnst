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
from lnst.Recipes.ENRT.MeasurementGenerators.FlowEndpointsStatCPUMeasurementGenerator import (
    FlowEndpointsStatCPUMeasurementGenerator,
)


class BaremetalEnrtRecipe(
    CommonPerfTestTweakMixin,
    DisableTurboboostMixin,
    DisableIdleStatesMixin,
    FlowEndpointsStatCPUMeasurementGenerator,
    IperfMeasurementGenerator,
    BaseEnrtRecipe,
):
    pass
