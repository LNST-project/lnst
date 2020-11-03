class BasePerfTestIterationTweakMixin(object):
    """
    This class is an extension to the :any:`Perf.Recipe` and defines common API
    for specific mixin classes that want to perform additional actions before
    each of the *perf test iterations*.

    The mixin classes should implement each of the methods in collaborative manner.
    """

    def generate_perf_test_iteration_tweak_description(self, perf_config):
        return ["Performance test iteration tweaks:"]

    def apply_perf_test_iteration_tweak(self, perf_config):
        perf_config.perf_test_iteration_tweak_config = {}

    def remove_perf_test_iteration_tweak(self, perf_config):
        # TODO: check if anything left in the perf_config.perf_test_iteration_tweak_config
        pass
