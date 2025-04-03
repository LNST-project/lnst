from lnst.Controller import HostReq, DeviceReq, RecipeParam


class DoubleTeamOrBondReq:
    host1 = HostReq()
    host1.eth0 = DeviceReq(
        label="tnet",
        driver=RecipeParam("driver"),
        speed=RecipeParam("nic_speed"),
        model=RecipeParam("nic_model"),
    )
    host1.eth1 = DeviceReq(
        label="tnet",
        driver=RecipeParam("driver"),
        speed=RecipeParam("nic_speed"),
        model=RecipeParam("nic_model"),
    )

    host2 = HostReq()
    host2.eth0 = DeviceReq(
        label="tnet",
        driver=RecipeParam("driver"),
        speed=RecipeParam("nic_speed"),
        model=RecipeParam("nic_model"),
    )
    host2.eth1 = DeviceReq(
        label="tnet",
        driver=RecipeParam("driver"),
        speed=RecipeParam("nic_speed"),
        model=RecipeParam("nic_model"),
    )
