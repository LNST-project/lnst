from lnst.Common.Parameters import StrParam


class EnrtDeviceReqParams():
    """
    This class groups all common parameters that are used in DeviceReq specifications
    of individual ENRT recipes.

    :param driver:
        The driver parameter is used to modify the hw network requirements,
        specifically to request Devices using the specified driver.

    :type driver: :any:`StrParam` (default is empty string that would match any interface in the MachinePool)

    :param nic_speed:
        The nic_speed parameter is used to modify the hw network requirements,
        specifically to request Devices that match the speed specified in the machine pool. 

    :type nic_speed: :any:`StrParam` (default is empty string)

    :param nic_model:
        The nic_model parameter is used to modify the hw network requirements,
        specifically to request Devices that match the model specified in the machine pool.

    :type nic_model: :any:`StrParam` (default is empty string)
    """

    driver = StrParam()
    nic_speed = StrParam()
    nic_model = StrParam()
