class BasePerfTestTweakMixin(object):
    """
    This is a base class that defines common API for specific *perf test*
    mixin classes.
    """

    def generate_perf_test_tweak_description(self, perf_config):
        return ["Performance test tweaks:"]

    def apply_perf_test_tweak(self, perf_config):
        perf_config.perf_test_tweak_config = {}

    def remove_perf_test_tweak(self, perf_config):
        # TODO: check if anything left in the perf_config.perf_test_tweak_config
        pass
