import pathlib
import time
from contextlib import contextmanager

from lnst.Common.LnstError import LnstError
from lnst.Common.Parameters import StrParam, IntParam, ChoiceParam
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Controller.Namespace import Namespace
from lnst.Controller.Recipe import BaseRecipe
from lnst.Controller.RecipeResults import ResultType
from lnst.RecipeCommon.TrafficControl import TrafficControlTester

class TcTestConfiguration:
    # Probably dont need this, to be used like EnrtConfiguration if its needed.
    pass

class TrafficControlRecipe(BaseRecipe):
    """
    Recipe to evaluate the performance of `tc filter` rule installs

    Primarily targetted towards testing mlx cards which support hardware and software steering
    """

    driver = StrParam(default="mlx5_core") # Need to figure out a way to handle variations in this driver name

    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    num_rules = IntParam(default=1000)

    steering_mode = ChoiceParam(type=StrParam, choices=["off", "smfs", "dmfs"], default="off")

    def test(self):
        with self._test_wide_context() :
            self.do_tc_test()

    @contextmanager
    def _test_wide_context(self):
        config = self.test_wide_configuration() # Do I have a use for this? Probably not
        #self.describe_test_wide_configuration(config)
        try:
            yield config
        finally:
            self.test_wide_deconfiguration(config)

    def test_wide_configuration(self):
        config = TcTestConfiguration()
        host = self.matched.host1

        # Send Tester class to agent.
        host.tc_tester: TrafficControlTester = host.init_class(TrafficControlTester, host.eth0.name)

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

    def test_wide_deconfiguration(self, config):
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

    def do_tc_test(self):
        host: Namespace = self.matched.host1

        success, time_taken, messages = host.tc_tester.run_test(self.params.num_rules)

        res = ResultType.PASS if success else ResultType.FAIL

        self.add_result(res, description=" ".join(messages), data={"time_taken": time_taken})

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
