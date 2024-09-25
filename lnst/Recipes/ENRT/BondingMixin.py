from lnst.Common.Parameters import (
    IntParam,
    StrParam,
    ChoiceParam,
)
from lnst.Devices import RemoteDevice, BondDevice
from lnst.Controller.Recipe import RecipeError


class BondingMixin:
    """
    The recipe mixin provides additional recipe parameters to configure the
    bonding device.

        :param bonding_mode:
            (mandatory test parameter) the bonding mode to be configured on
            the bond0 device.
        :param miimon_value:
            (mandatory test parameter) the miimon interval to be configured
            on the bond0 device.
        :param fail_over_mac:
            the fail_over_mac mode to be configured on the bond0 device.
    """
    bonding_mode = StrParam(mandatory=True)
    miimon_value = IntParam(mandatory=True)
    fail_over_mac = ChoiceParam(
        StrParam, choices={"none", "active", "follow"}, default="none"
    )

    def create_bond_devices(
        self, bond_devices_specs: dict[str: dict[str: list[RemoteDevice]]] = {}
    ) -> None:
        """
        The derived class should call:
        ```
        self.create_bond_devices(
            {
                "host1": {
                    "bond0": [host1.nic1, host1.nic2]
                },
                "host2": {
                    "bond0": [host2.nic1, host2.nic2]
                }
            }

        That would create devices accessible by host1.bond0 and host2.bond0
        )
        ```
        """
        device_params = dict(
            mode=self.params.bonding_mode,
            miimon=self.params.miimon_value,
        )

        if self.params.bonding_mode in ["active-backup", "1"]:
            device_params["fail_over_mac"] = self.params.fail_over_mac

        for host_str, spec in bond_devices_specs.items():
            for bond_dev_name, bonded_devices in spec.items():
                if len({dev.host for dev in bonded_devices}) > 1:
                    raise RecipeError(
                        f"Cannot create bond device with ports coming from different hosts, {bonded_devices}"
                    )

                host = getattr(self.matched, host_str)
                setattr(host, bond_dev_name, BondDevice(**device_params))
                bond_device = getattr(host, bond_dev_name)
                for dev in bonded_devices:
                    dev.down()
                    bond_device.slave_add(dev)
