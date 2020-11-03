from lnst.Common.Parameters import BoolParam
from lnst.RecipeCommon.Perf.PerfTestMixins import BasePerfTestIterationTweakMixin


class DropCachesPerfTestMixin(BasePerfTestIterationTweakMixin):
    """
    This mixin class is an extension to the :any:`BaseEnrtRecipe` class that can
    be used to drop vm caches before running each iteration of the performance
    measurements.

    :param drop_caches:
        (optional test parameter) a boolean, if set to True, the memory caches
        are dropped otherwise the mixin has no effect
    """

    drop_caches = BoolParam(default=False)

    def generate_perf_test_iteration_tweak_description(self, perf_config):
        description = super().generate_perf_test_iteration_tweak_description(
            perf_config
        )
        if self.params.drop_caches:
            for host in self.matched:
                description.append(
                    "dropped vm caches before iteration on host {}".format(host.hostid)
                )
        else:
            description.append("skipped dropping vm caches before iteration")
        return description

    def apply_perf_test_iteration_tweak(self, perf_config):
        super().apply_perf_test_iteration_tweak(perf_config)

        if self.params.drop_caches:
            for host in self.matched:
                host.run("echo 1 > /proc/sys/vm/drop_caches")

    def remove_perf_test_iteration_tweak(self, perf_config):
        super().remove_perf_test_iteration_tweak(perf_config)
