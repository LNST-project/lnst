from lnst.Controller import HostReq, DeviceReq, RecipeParam


class PvPReq:
    host1 = HostReq()
    host1.eth0 = DeviceReq(
        label="net1",
        driver=RecipeParam("driver"),
        speed=RecipeParam("nic_speed"),
        model=RecipeParam("nic_model"),
    )
    host1.eth1 = DeviceReq(
        label="net1",
        driver=RecipeParam("driver"),
        speed=RecipeParam("nic_speed"),
        model=RecipeParam("nic_model"),
    )

    host2 = HostReq(with_guest="yes")
    host2.eth0 = DeviceReq(
        label="net1",
        driver=RecipeParam("driver"),
        speed=RecipeParam("nic_speed"),
        model=RecipeParam("nic_model"),
    )
    host2.eth1 = DeviceReq(
        label="net1",
        driver=RecipeParam("driver"),
        speed=RecipeParam("nic_speed"),
        model=RecipeParam("nic_model"),
    )
