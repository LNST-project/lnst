from lnst.Controller import HostReq, DeviceReq, RecipeParam


class SimpleNetworkReq:
    host1 = HostReq()
    host1.eth0 = DeviceReq(
        label="net1",
        driver=RecipeParam("driver"),
        speed=RecipeParam("nic_speed"),
        model=RecipeParam("nic_model"),
    )

    host2 = HostReq()
    host2.eth0 = DeviceReq(
        label="net1",
        driver=RecipeParam("driver"),
        speed=RecipeParam("nic_speed"),
        model=RecipeParam("nic_model"),
    )
