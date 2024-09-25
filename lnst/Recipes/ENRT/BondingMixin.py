from lnst.Common.Parameters import (
    IntParam,
    StrParam,
    ChoiceParam,
)
from lnst.Devices import RemoteDevice, BondDevice
from lnst.Controller.Recipe import RecipeError
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration


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
        self,
        config: EnrtConfiguration,
        bond_devices_specs: dict[str: dict[str: list[RemoteDevice]]] = {}
    ) -> None:
        """
        The derived class should call:

        .. code-block:: none

            config = super().test_wide_configuration()
            self.create_bond_devices(
                config,
                {
                    "host1": {
                        "bond0": [host1.nic1, host1.nic2]
                    },
                    "host2": {
                        "bond0": [host2.nic1, host2.nic2]
                    }
                }
            )

        That would create bonding devices accessible by `host1.bond0` and `host2.bond0`.

        `host1.bond0` would be created with ports `host1.nic1` and `host1.nic2` and
        `host2.bond0` with ports `host2.nic1` and `host2.nic2`.
        """
        device_params = dict(
            mode=self.params.bonding_mode,
            miimon=self.params.miimon_value,
        )

        if self.params.bonding_mode in ["active-backup", "1"]:
            device_params["fail_over_mac"] = self.params.fail_over_mac

        config.bonding_config = {}
        for host_str, spec in bond_devices_specs.items():
            for bond_dev_name, bonded_devices in spec.items():
                try:
                    host = getattr(self.matched, host_str)
                except AttributeError:
                    raise RecipeError(
                        f"Bond device specification contains unknown host {host_str}"
                    )

                if any([dev.host.hostid != host_str for dev in bonded_devices]):
                    raise RecipeError(
                        f"Attempt to create bond device on host {host_str} with some ports that are not available on the host, ports: {bonded_devices}"
                    )

                setattr(host, bond_dev_name, BondDevice(**device_params))
                bond_device = getattr(host, bond_dev_name)
                for dev in bonded_devices:
                    dev.down()
                    bond_device.slave_add(dev)

                config.bonding_config.setdefault("bond_devices", []).append(bond_device)

    def test_wide_deconfiguration(self, config):
        config.bonding_config.clear()

    def generate_test_wide_description(self, config: EnrtConfiguration):
        desc = super().generate_test_wide_description(config)
        bond_devices = config.bonding_config["bond_devices"]
        for dev in bond_devices:
            desc += [
                "\n".join(
                    [
                        "Configured {}.{}.ports = {}".format(
                            dev.host.hostid, dev.name,
                            ['.'.join([dev.host.hostid, port.name])
                             for port in dev.slaves]
                        )
                    ],
                ),
                "Configured {}.{}.mode = {}".format(
                    dev.host.hostid, dev.name,
                    dev.mode
                ),
                "Configured {}.{}.miimon = {}".format(
                    dev.host.hostid, dev.name,
                    dev.miimon
                ),
            ]

            if dev.mode == 1:
                desc += [
                    "Configured {}.{}.fail_over_mac = {}".format(
                        dev.host.hostid, dev.name, dev.fail_over_mac
                    )
                ]

        return desc
