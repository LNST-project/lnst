from lnst.Common.Parameters import BoolParam
from lnst.Controller.Requirements import DeviceReq
from lnst.Recipes.ENRT.SRIOVDevices import SRIOVDevices


class UseVfsMixin:
    """
    Mixin allows any ENRT recipe to use virtual function (VF) interfaces
    instead of physical interfaces defined by DeviceReq requirements.

    VF interfaces are created automatically and DeviceReq handles are replaced
    with VF Device instances. This allows user to interact with the network
    interfaces without additional changes to the code of recipe.

    There are some limitations, for example pause frames cannot be configured
    since the VF do not support these.
    """

    use_vfs = BoolParam(default=False)

    def test_wide_configuration(self):
        config = super().test_wide_configuration()

        if not self.params.use_vfs:
            return config

        config.vf_config = {}
        for host_key, host_req in self.req:
            dev_names = [key for key, value in host_req if isinstance(value, DeviceReq)]
            host = getattr(self.matched, host_key)

            # remap_pfs_to_vfs
            for dev_name in dev_names:
                dev = getattr(host, dev_name)
                sriov_devices = SRIOVDevices(dev, 1)
                vf_dev = sriov_devices.vfs[0]
                host.map_device(dev_name, {"ifname": vf_dev.name})

                host_config = config.vf_config.setdefault(host, [])
                host_config.append(sriov_devices)

        return config

    def test_wide_deconfiguration(self, config):
        if self.params.use_vfs:
            for host, sriov_devices_list in config.vf_config.items():
                for sriov_devices in sriov_devices_list:
                    vf_dev = sriov_devices.vfs[0]
                    host.map_device(vf_dev._id, {"ifname": sriov_devices.phys_dev.name})
                    sriov_devices.phys_dev.delete_vfs()

        super().test_wide_deconfiguration(config)
