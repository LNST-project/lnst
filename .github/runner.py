from lnst.Controller import Controller, HostReq, DeviceReq, BaseRecipe
from lnst.Controller.ContainerPoolManager import ContainerPoolManager
from lnst.Controller.MachineMapper import ContainerMapper


class HelloWorldRecipe(BaseRecipe):
    machine1 = HostReq()
    machine1.nic1 = DeviceReq(label="net1")

    machine2 = HostReq()
    machine2.nic1 = DeviceReq(label="net1")

    def test(self):
        self.matched.machine1.nic1.ip_add("192.168.1.1/24")
        self.matched.machine1.nic1.up()
        self.matched.machine2.nic1.ip_add("192.168.1.2/24")
        self.matched.machine2.nic1.up()

        self.matched.machine1.run("ping 192.168.1.2 -c 5")
        self.matched.machine2.run("ping 192.168.1.1 -c 5")


podman_uri = "unix:///run/podman/podman.sock"
image_name = "lnst"
ctl = Controller(
    poolMgr=ContainerPoolManager,
    mapper=ContainerMapper,
    podman_uri=podman_uri,
    image=image_name,
    debug=1,
    network_plugin="custom_lnst",
)

recipe_instance = HelloWorldRecipe()
ctl.run(recipe_instance)

overall_result = all([run.overall_result for run in recipe_instance.runs])

exit(not overall_result)
