import pathlib
import time
from contextlib import contextmanager

from lnst.Common.LnstError import LnstError
from lnst.Common.Parameters import ListParam, StrParam, IntParam, ChoiceParam
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Controller.Namespace import Namespace
from lnst.RecipeCommon import BaseResultEvaluator
from lnst.RecipeCommon.Perf.Evaluators.MaxTimeTakenEvaluator import MaxTimeTakenEvaluator
from lnst.RecipeCommon.Perf.Measurements import StatCPUMeasurement
from lnst.RecipeCommon.Perf.Measurements.TcRunMeasurement import TcRunMeasurement
from lnst.RecipeCommon.Perf.Recipe import RecipeConf, Recipe as PerfRecipe, RecipeResults


class TcRecipeConfiguration(RecipeConf):
    pass


class TrafficControlRecipe(PerfRecipe):
    """
    Recipe to evaluate the performance of `tc filter` rule installs

    Primarily targeted towards testing mlx cards which support hardware and software steering
    """

    driver = StrParam(default="mlx5_core")

    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    num_rules = IntParam(default=1000)
    parallel_instances = IntParam(default=4)
    cpu_bind = ListParam(type=IntParam())
    cpu_bind_policy = ChoiceParam(type=StrParam, choices={"all", "round-robin"}, default="round-robin")

    steering_mode = ChoiceParam(
        type=StrParam,
        choices=["off", "smfs", "dmfs"],
        default="off",
    )

    def test(self):
        with self._test_wide_context() as config:
            self.do_tc_test_perf_recipe(config)

    @contextmanager
    def _test_wide_context(self):
        config = self.test_wide_configuration()
        try:
            yield config
        finally:
            self.test_wide_deconfiguration(config)

    def test_wide_configuration(self) -> TcRecipeConfiguration:
        host = self.matched.host1
        cpu_measurement = StatCPUMeasurement(
            hosts=[host],
        )
        measurement = TcRunMeasurement(
            device=host.eth0,
            num_instances=self.params.parallel_instances,
            rules_per_instance=self.params.num_rules,
            cpu_bind=self.params.cpu_bind,
            cpu_bind_policy=self.params.cpu_bind_policy,
        )
        config = TcRecipeConfiguration(
           measurements=[cpu_measurement, measurement],
           iterations=1,
       )
        config.register_evaluators(measurement, self.tc_run_evaluators)

        # Enable steering if its needed
        if self.is_steering_test:
            host.run(f"devlink dev param set pci/{host.eth0.bus_info} "
                     f"name flow_steering_mode value \"{self.params.steering_mode}\" cmode runtime")

        self.vf_setup()

        # Switch to switchdev mode
        host.run(f"devlink dev eswitch set pci/{host.eth0.bus_info} mode switchdev")


        # init ingress qdisc
        #  This might fail, we might not need it because lnst deletes it on device teardown
        host.run(f"tc qdisc del dev {host.eth0.name} ingress | true")
        host.run(f"tc qdisc add dev {host.eth0.name} ingress")

        return config

    def test_wide_deconfiguration(self, config: TcRecipeConfiguration):
        """
        Cleanup:
        tc filter del dev ens5f0np0 ingress
        devlink dev eswitch set pci/$pci mode legacy
        echo 0 > /sys/bus/pci/devices/$pci/sriov_numvfs
        """
        host: Namespace = self.matched.host1

        host.run(f"tc filter del dev {host.eth0.name} ingress") # Probably not needed, it seems to be done by lnst device class
        host.run(f"echo 0 > /sys/class/net/{host.eth0.name}/device/sriov_numvfs")
        time.sleep(2)
        host.run(f"devlink dev eswitch set pci/{host.eth0.bus_info} mode legacy")
        time.sleep(3)

    def do_tc_test_perf_recipe(self, test_config):
        results = self.perf_test(test_config)
        self.perf_report_and_evaluate(results)

    def perf_report_and_evaluate(self, results: RecipeResults):
        # Override result alignment
        self.perf_report(results)
        self.perf_evaluate(results)

    @property
    def tc_run_evaluators(self) -> list[BaseResultEvaluator]:
        return [MaxTimeTakenEvaluator(100)]

    @property
    def is_steering_test(self) -> bool:
        if self.params.steering_mode in ["smfs", "dmfs"]:
            if self.params.driver.startswith("mlx5"):
                return True
            else:
                raise LnstError(f"Unsupported driver {self.params.driver} for steering")
        return False

    def vf_setup(self):
        host1: Namespace = self.matched.host1
        # Create virtual func
        host1.run(
            f"echo 1 > /sys/bus/pci/devices/{host1.eth0.bus_info}/sriov_numvfs "
        )

        #Unbind the interfaces they create
        # Need to see if there is a better way to do this.
        vf_pci = host1.run(f"readlink /sys/bus/pci/devices/{host1.eth0.bus_info}/virtfn0")
        vf_pci = pathlib.PurePath(vf_pci.stdout.rstrip()).name
        host1.run(f"echo {vf_pci} > /sys/bus/pci/devices/{host1.eth0.bus_info}/virtfn0/driver/unbind")

    def apply_perf_test_tweak(self, config):
        pass

    def describe_perf_test_tweak(self, config):
        pass

    def remove_perf_test_tweak(self, config):
        pass
