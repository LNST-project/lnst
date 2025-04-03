from lnst.Controller import HostReq, DeviceReq, RecipeParam


class VirtualBridgeReq:
    host1 = HostReq()
    host1.eth0 = DeviceReq(
        label="to_switch",
        driver=RecipeParam("driver"),
        speed=RecipeParam("nic_speed"),
        model=RecipeParam("nic_model"),
    )
    host1.tap0 = DeviceReq(label="to_guest")

    host2 = HostReq()
    host2.eth0 = DeviceReq(
        label="to_switch",
        driver=RecipeParam("driver"),
        speed=RecipeParam("nic_speed"),
        model=RecipeParam("nic_model"),
    )

    guest1 = HostReq()
    guest1.eth0 = DeviceReq(label="to_guest")
