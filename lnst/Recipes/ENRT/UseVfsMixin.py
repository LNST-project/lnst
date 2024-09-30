from lnst.Common.Parameters import BoolParam, ChoiceParam
from lnst.Controller.Requirements import DeviceReq
from lnst.Recipes.ENRT.SRIOVDevices import SRIOVDevices
from lnst.Devices import RemoteDevice


class UseVfsMixin:
    """
    Mixin allows any ENRT recipe to use virtual function (VF) interfaces
    instead of physical interfaces defined by DeviceReq requirements.

    VF interfaces are created automatically and DeviceReq handles are replaced
    with VF Device instances. This allows user to interact with the network
    interfaces without additional changes to the code of recipe.

    Mixin provides two parameters:
    * use_vfs - main boolean parameter to enable or disable (default) use of VFs
    * vf_trust - (optional) set the trust parameter of the used VFs, 'on' or 'off'

    There are some limitations, for example pause frames cannot be configured
    since the VF do not support these.
    """

    use_vfs = BoolParam(default=False)
    vf_trust = ChoiceParam(choices={'on', 'off'})

    def test_wide_configuration(self):
        config = super().test_wide_configuration()

        if not self.params.use_vfs:
            return config

        self.vf_config = {}
        for host_key, host_req in self.req:
            dev_names = [key for key, value in host_req if isinstance(value, DeviceReq)]
            host = getattr(self.matched, host_key)

            # remap_pfs_to_vfs
            for dev_name in dev_names:
                dev = getattr(host, dev_name)
                sriov_devices = SRIOVDevices(dev, 1)

                vf_dev = sriov_devices.vfs[0]
                host.map_device(dev_name, {"ifname": vf_dev.name})

                host_config = self.vf_config.setdefault(host, [])
                host_config.append(sriov_devices)

        if self.params.get("vf_trust"):
            for dev in self.vf_trust_device_list:
                dev.vf_trust(0, self.params.vf_trust)

        return config

    def test_wide_deconfiguration(self, config):
        if self.params.use_vfs:
            for host, sriov_devices_list in self.vf_config.items():
                for sriov_devices in sriov_devices_list:
                    vf_dev = sriov_devices.vfs[0]
                    host.map_device(vf_dev._id, {"ifname": sriov_devices.phys_dev.name})
                    sriov_devices.phys_dev.delete_vfs()

        super().test_wide_deconfiguration(config)

    def generate_test_wide_description(self, config):
        description = super().generate_test_wide_description(config)

        if self.params.use_vfs:
            description += [
                f"Using vf device {vf_dev.name} of pf {sriov_devices.phys_dev.name} for DeviceReq {host.hostid}.{vf_dev._id}" + (f" trusted={self.params.vf_trust}" if self.params.get("vf_trust") and sriov_devices.phys_dev in self.vf_trust_device_list else "")
                for host, sriov_devices_list in self.vf_config.items()
                for sriov_devices in sriov_devices_list
                for vf_dev in sriov_devices.vfs
            ]

        return description

    @property
    def vf_trust_device_list(self) -> list[RemoteDevice]:
        return []
