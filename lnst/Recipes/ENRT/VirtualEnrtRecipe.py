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
