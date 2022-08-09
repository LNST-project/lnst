import pprint
import copy
from contextlib import contextmanager

from lnst.Common.LnstError import LnstError
from lnst.Common.Parameters import (
    Param,
    IntParam,
    StrParam,
    BoolParam,
    FloatParam,
)
from lnst.Common.IpAddress import AF_INET, AF_INET6
from lnst.Controller.RecipeResults import ResultType
from lnst.Recipes.ENRT.ConfigMixins.BaseSubConfigMixin import BaseSubConfigMixin
from lnst.Recipes.ENRT.MeasurementGenerators.BaseMeasurementGenerator import (
    BaseMeasurementGenerator,
)

from lnst.RecipeCommon.Ping.Recipe import PingTestAndEvaluate, PingConf
from lnst.RecipeCommon.Perf.Recipe import Recipe as PerfRecipe
from lnst.RecipeCommon.Perf.Recipe import RecipeConf as PerfRecipeConf
from lnst.RecipeCommon.Perf.Measurements.BaseCPUMeasurement import BaseCPUMeasurement
from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import BaseFlowMeasurement
from lnst.RecipeCommon.Perf.Evaluators import NonzeroFlowEvaluator
from lnst.RecipeCommon.Ping.Evaluators import RatePingEvaluator

class EnrtConfiguration(object):
    """Container object for configuration

    Intentionally left empty as it is intended to be used as a container to
    store any values relevant to configuration being applied during the lifetime
    of the Recipe.
    """
    pass


class BaseEnrtRecipe(
    BaseSubConfigMixin,
    BaseMeasurementGenerator,
    PingTestAndEvaluate,
    PerfRecipe,
):
    """Base Recipe class for the ENRT recipe package

    This class defines the shared *test* method defining the common test
    procedure in a very generic way. This common test procedure involves a
    single main *test_wide* configuration that is different for every specific
    scenario. After the main configuration there is usually a loop of several
    minor *sub* configrations types that can take different values to slightly
    change the tested use cases.

    Finally, for each combination of a **test_wide** + **sub** configuration we
    do a several ping connection test and several performance measurement tests.

    **test_wide** and **sub** configurations are implemented with **context
    manager** methods which ensure that if any exceptions are raised (for
    example because of a bug in the recipe) that deconfiguration is called.

    Both **test_wide** and **sub** configurations are to be implemented in
    different classes, the BaseEnrtRecipe class only defines the common API and
    the base versions of the relevant methods.

    Test wide configuration is implemented via the following methods:

    * :any:`test_wide_configuration`
    * :any:`test_wide_deconfiguration`
    * :any:`generate_test_wide_description`

    Sub configurations are **mixed into** classes defining the specific
    scenario that is being tested. Various sub configurations are implemented as
    individual Python **Mixin** classes in the
    :any:`ConfigMixins<config_mixins>` package. These make use of Pythons
    collaborative inheritance by calling the `super` function in a specific way.
    The "machinery" for that is defined in the :any:`BaseSubConfigMixin` class.
    It is then used in this class from the `test` method loop.

    :param driver:
        The driver parameter is used to modify the hw network requirements,
        specifically to request Devices using the specified driver. This is
        common enough in the Enrt recipes that it can be part of the Base class.

    :type driver: :any:`StrParam` (default "ixgbe")

    :param ip_versions:
        Parameter that determines which IP protocol versions will be tested.
    :type ip_versions: Tuple[Str] (default ("ipv4", "ipv6"))

    :param ping_parallel:
        Parameter used by the :any:`generate_ping_configurations` generator.
        Tells the generator method to create :any:`PingConf` objects that will
        be run in parallel.
    :type ping_parallel: :any:`BoolParam` (default False)

    :param ping_bidirect:
        Parameter used by the :any:`generate_ping_configurations` generator.
        Tells the generator method to create :any:`PingConf` objects for both
        directions between the ping endpoints.
    :type ping_bidirect: :any:`BoolParam` (default False)

    :param ping_count:
        Parameter used by the :any:`generate_ping_configurations` generator.
        Tells the generator how many pings should be sent for each ping test.
    :type ping_count: :any:`IntParam` (default 100)

    :param ping_interval:
        Parameter used by the :any:`generate_ping_configurations` generator.
        Tells the generator how fast should the pings be sent in each ping test.
    :type ping_interval: :any:`FloatParam` (default 0.2)

    :param ping_psize:
        Parameter used by the :any:`generate_ping_configurations` generator.
        Tells the generator how big should the pings packets be in each ping
        test.
    :type ping_psize: :any:`IntParam` (default None)

    :param net_perf_tool:
        Parameter used by the :any:`generate_perf_configurations` generator to
        create a PerfRecipeConf object.
        Specifies a network flow measurement class that accepts :any:`PerfFlow`
        objects and can be used to measure those specified flows
    :type net_perf_tool: :any:`BaseFlowMeasurement` (default
        IperfFlowMeasurement)

    :param cpu_perf_tool:
        Parameter used by the :any:`generate_perf_configurations` generator to
        create a PerfRecipeConf object.
        Specifies a cpu measurement class that can be used to measure CPU
        utilization on specified hosts.
    :type cpu_perf_tool: :any:`BaseCPUMeasurement` (default StatCPUMeasurement)

    :param perf_evaluation_strategy:
        Parameter used by the :any:`evaluator_by_measurement` selector to
        pick correct performance measurement evaluators based on the strategy
        specified.
    :type perf_evaluation_strategy: :any:`StrParam` (default "all")
    """

    driver = StrParam(default="ixgbe")

    #common test parameters
    ip_versions = Param(default=("ipv4", "ipv6"))

    #common ping test params
    ping_parallel = BoolParam(default=False)
    ping_bidirect = BoolParam(default=False)
    ping_count = IntParam(default=100)
    ping_interval = FloatParam(default=0.2)
    ping_psize = IntParam(default=56)

    # generic perf test params
    perf_evaluation_strategy = StrParam(default="all")

    def test(self):
        """Main test loop shared by all the Enrt recipes

        The test loop involves a single application of a **test_wide**
        configuration, then a loop over multiple **sub** configurations that
        involves:

        * creating the combined sub configuration of all available SubConfig
          Mixin classes via :any:`generate_sub_configurations`
        * applying the generated sub configuration via the :any:`_sub_context`
          context manager method
        * running tests
        * removing the current sub configuration via the :any:`_sub_context`
          context manager method
        """
        with self._test_wide_context() as main_config:
            for sub_config in self.generate_sub_configurations(main_config):
                with self._sub_context(sub_config) as recipe_config:
                    self.do_tests(recipe_config)

    @contextmanager
    def _test_wide_context(self):
        config = self.test_wide_configuration()
        self.describe_test_wide_configuration(config)
        try:
            yield config
        finally:
            self.test_wide_deconfiguration(config)

    def test_wide_configuration(self):
        """Creates an empty :any:`EnrtConfiguration` object

        This is again used in potential collaborative inheritance design that
        may potentially be useful for Enrt recipes. Derived classes will each
        individually add their own values to the instance created here. This way
        the complete test wide configuration is tracked in a single object.

        :return: returns a config object that tracks the applied configuration
            that can be used during testing to inspect the current state and
            make test decisions based on it.
        :rtype: :any:`EnrtConfiguration`

        Example::

            class Derived:
                def test_wide_configuration():
                    config = super().test_wide_configuration()

                    # ... configure something
                    config.something = what_was_configured

                    return config
        """
        return EnrtConfiguration()

    def test_wide_deconfiguration(self, config):
        """Base deconfiguration method.

        In the base class this should maybe only check if there's any leftover
        configuration and warn about it. In derived classes this can be
        overriden to take care of deconfiguring what was configured in the
        respective test_wide_configuration method.

        Example::

            class Derived:
                def test_wide_deconfiguration(config):
                    # ... deconfigure something
                    del config.something #cleanup tracking

                    return super().test_wide_deconfiguration()
        """
        #TODO check if anything is still applied and throw exception?
        return

    def describe_test_wide_configuration(self, config):
        """Describes the current test wide configuration

        Creates a new result object that contains the description of the full
        test wide configuration applied by all the
        :any:`test_wide_configuration` methods in the class hierarchy.

        The description needs to be generated by the
        :any:`generate_test_wide_description` method. Additionally the
        description contains the state of all the parameters and their values
        passed to the recipe class instance during initialization.
        """
        description = self.generate_test_wide_description(config)
        self.add_result(ResultType.PASS, "Summary of used Recipe parameters:\n{}".format(
                        pprint.pformat(self.params._to_dict())))
        self.add_result(ResultType.PASS, "\n".join(description))

    def generate_test_wide_description(self, config):
        """Generates the test wide configuration description

        Another class inteded to be used with the collaborative version of the
        `super` method to cumulatively desribe the full test wide configuration
        that was applied through multiple classes.

        The base class version of this method creates the initial list of
        strings containing just the header line. Each string added to this list
        will later be printed on its own line.

        :return: list of strings, each representing a single line
        :rtype: List[str]

        Example::

            class Derived:
                def generate_sub_configuration_description(config):
                    desc = super().generate_sub_configuration_description(config)
                    desc.append("Configured something: {}".format(config.something))
                    return desc
        """
        return [
            "Testwide configuration for recipe {} description:".format(
                self.__class__.__name__
            )
        ]

    @contextmanager
    def _sub_context(self, config):
        self.apply_sub_configuration(config)
        self.describe_sub_configuration(config)
        try:
            yield config
        finally:
            self.remove_sub_configuration(config)

    def describe_sub_configuration(self, config):
        description = self.generate_sub_configuration_description(config)
        self.add_result(ResultType.PASS, "\n".join(description))

    def do_tests(self, recipe_config):
        """Entry point for actual tests

        The common scenario is to do ping and performance tests, however the
        method can be overriden to add more tests if needed.
        """
        self.do_ping_tests(recipe_config)
        self.do_perf_tests(recipe_config)

    def do_ping_tests(self, recipe_config):
        """Ping testing loop

        Loops over all various ping configurations generated by the
        :any:`generate_ping_configurations` method, then uses the PingRecipe
        methods to execute, report and evaluate the results.
        """
        for ping_configs in self.generate_ping_configurations(recipe_config):
            result = self.ping_test(ping_configs)
            self.ping_report_and_evaluate(result)

    def describe_perf_test_tweak(self, perf_config):
        description = self.generate_perf_test_tweak_description(perf_config)
        self.add_result(ResultType.PASS, "\n".join(description))

    def do_perf_tests(self, recipe_config):
        """Performance testing loop

        Loops over all various perf configurations generated by the
        :any:`generate_perf_configurations` method, then uses the PerfRecipe
        methods to execute, report and evaluate the results.
        """
        for perf_config in self.generate_perf_configurations(recipe_config):
            result = self.perf_test(perf_config)
            self.perf_report_and_evaluate(result)

    def generate_ping_configurations(self, config):
        """Base ping test configuration generator

        The generator loops over all endpoint pairs to test ping between
        (generated by the :any:`generate_ping_endpoints` method) then over all
        the selected :any:`ip_versions` and finally over all the IP addresses
        that fit those criteria.

        :return: list of Ping configurations to test in parallel
        :rtype: List[:any:`PingConf`]
        """
        for endpoints in self.generate_ping_endpoints(config):
            for ipv in self.params.ip_versions:
                if ipv == "ipv6" and not endpoints.reachable:
                    continue

                ip_filter = {}
                if ipv == "ipv4":
                    ip_filter.update(family = AF_INET)
                elif ipv == "ipv6":
                    ip_filter.update(family = AF_INET6)
                    ip_filter.update(is_link_local = False)

                endpoint1, endpoint2 = endpoints.endpoints
                endpoint1_ips = endpoint1.ips_filter(**ip_filter)
                endpoint2_ips = endpoint2.ips_filter(**ip_filter)

                if len(endpoint1_ips) != len(endpoint2_ips):
                    raise LnstError("Source/destination ip lists are of different size.")

                ping_conf_list = []
                for src_addr, dst_addr in zip(endpoint1_ips, endpoint2_ips):
                    pconf = PingConf(client = endpoint1.netns,
                                     client_bind = src_addr,
                                     destination = endpoint2.netns,
                                     destination_address = dst_addr,
                                     count = self.params.ping_count,
                                     interval = self.params.ping_interval,
                                     size = self.params.ping_psize,
                                     )

                    ping_evaluators = self.generate_ping_evaluators(
                            pconf, endpoints)
                    pconf.register_evaluators(ping_evaluators)

                    ping_conf_list.append(pconf)

                    if self.params.ping_bidirect:
                        ping_conf_list.append(self._create_reverse_ping(pconf))

                    if not self.params.ping_parallel:
                        break

                yield ping_conf_list

    def generate_ping_endpoints(self, config):
        """Generator for ping endpoints

        To be overriden by a derived class.

        :return: list of device pairs
        :rtype: List[Tuple[:any:`Device`, :any:`Device`]]
        """
        return []

    def generate_ping_evaluators(self, pconf, endpoints):
        return [RatePingEvaluator(min_rate=50)]

    def generate_perf_configurations(self, config):
        """Base perf test configuration generator

        The generator loops over all flow combinations to measure performance
        for (generated by the :any:`generate_flow_combinations` method). In
        addition to that during each flow combination measurement we add CPU
        utilization measurement to run on the background.

        Finally for each generated perf test configuration we register
        measurement evaluators based on the :any:`cpu_perf_evaluators` and
        :any:`net_perf_evaluators` properties.

        :return: list of Perf test configurations
        :rtype: List[:any:`PerfRecipeConf`]
        """
        for measurements in self.generate_perf_measurements_combinations(
            config
        ):
            perf_conf = PerfRecipeConf(
                measurements=measurements,
                iterations=self.params.perf_iterations,
                parent_recipe_config=copy.deepcopy(config),
            )
            self.register_perf_evaluators(perf_conf)

            yield perf_conf

    def register_perf_evaluators(self, perf_conf):
        """Registrator for perf evaluators

        The registrator loops over all measurements collected by the
        perf tests to pick evaluator based on the measurements using
        the :any:`evaluator_by_measurement` method.

        Once appropriate evaluator is picked, it is registered to
        the :any:`PerfRecipeConf`.
        """
        for measurement in perf_conf.measurements:
            evaluators = self.evaluator_by_measurement(measurement)
            perf_conf.register_evaluators(measurement, evaluators)

    def evaluator_by_measurement(self, measurement):
        """Selector for the evaluators based on measurements

        The selector looks at the input measurement to pick
        appropriate evaluator.

        If :any: `perf_evaluation_strategy` property is set
        to either "none" or "nonzero", selector returns
        given evaluators based on their strategy.

        :return: list of Result evaluators
        :rtype: List[:any:`BaseResultEvaluator`]

        """
        if self.params.perf_evaluation_strategy == "none":
            return []

        if isinstance(measurement, BaseCPUMeasurement):
            if self.params.perf_evaluation_strategy in ["nonzero", "none"]:
                evaluators = []
            else:
                evaluators = self.cpu_perf_evaluators
        elif isinstance(measurement, BaseFlowMeasurement):
            if self.params.perf_evaluation_strategy == "nonzero":
                evaluators = [NonzeroFlowEvaluator()]
            else:
                evaluators = self.net_perf_evaluators
        else:
            evaluators = []

        return evaluators

    @property
    def cpu_perf_evaluators(self):
        """CPU measurement evaluators

        To be overriden by a derived class. Returns the list of evaluators to
        use for CPU utilization measurement evaluation.

        :return: a list of cpu evaluator objects
        :rtype: List[BaseEvaluator]
        """
        return []

    @property
    def net_perf_evaluators(self):
        """Network flow measurement evaluators

        To be overriden bby a derived class. Returns the list of evaluators to
        use for Network flow measurement evaluation.

        :return: a list of flow evaluator objects
        :rtype: List[BaseEvaluator]
        """
        return [NonzeroFlowEvaluator()]

    def wait_tentative_ips(self, devices):
        def condition():
            return all(
                [not ip.is_tentative for dev in devices for ip in dev.ips]
            )

        self.ctl.wait_for_condition(condition, timeout=5)

    def _create_reverse_ping(self, pconf):
        return PingConf(
            client = pconf.destination,
            client_bind = pconf.destination_address,
            destination = pconf.client,
            destination_address = pconf.client_bind,
            count = pconf.ping_count,
            interval = pconf.ping_interval,
            size = pconf.ping_psize,
        )
