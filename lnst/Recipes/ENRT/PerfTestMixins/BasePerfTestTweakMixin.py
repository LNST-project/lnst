class BasePerfTestTweakMixin(object):
    """
    This is a base class that defines common API for specific *perf test*
    mixin classes.
    """

    def apply_perf_test_tweak(self, perf_config):
        pass

    def remove_perf_test_tweak(self, perf_config):
        pass
