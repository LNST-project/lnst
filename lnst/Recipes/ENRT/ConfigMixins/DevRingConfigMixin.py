from json import loads
from lnst.Common.Parameters import DictParam
from lnst.Recipes.ENRT.ConfigMixins.BaseHWConfigMixin import BaseHWConfigMixin


class DevRingConfigMixin(BaseHWConfigMixin):
    """
    This class extends :any:`BaseEnrtRecipe` class that
    enables configuration of device ring settings.

    Example configration:

    .. code-block:: python

        dev_ring_config = {
            "host1": {
                "eth1": {
                    "rx": 1024,
                    "tx": 1024,
                    }
            },
            "host2": {
                "eth1": {
                    "rx": 512,
                    "tx": 512,
                },
            },
        }

    """
    dev_ring_config = DictParam(mandatory=False)

    def hw_config(self, config):
        super().hw_config(config)

        hw_config = config.hw_config

        if self.params.get("dev_ring_config"):
            hw_config["dev_ring_config"] = {}
            self._configure_rings(hw_config)

    def _configure_rings(self, hw_config):
        device_settings = self._parse_device_settings(self.params.dev_ring_config)
        for device, ring_configs in device_settings.items():
            # Get original ring config
            ethtool_job = device.host.run(f"ethtool --json -g {device.name}")
            original_config = process_ring_settings_output(
                ethtool_job.stdout, [configured for configured in ring_configs.keys()]
            )

            hw_config["dev_ring_config"][device] = {
                "original": original_config,
            }

            # Set ring settings
            device.host.run(
                f"ethtool -G {device.name} "
                + " ".join(
                    ring_cfg_name + " " + str(ring_cfg_value)
                    for ring_cfg_name, ring_cfg_value in ring_configs.items()
                )
            )

            hw_config["dev_ring_config"][device]["configured"] = ring_configs

    def hw_deconfig(self, config):
        # Restore ring configs
        dev_ring_config = config.hw_config.get("dev_ring_config", {})
        for dev, dev_ring_config in dev_ring_config.items():
            configured_config = dev_ring_config.get("configured", {})
            original_config = dev_ring_config.get("original", {})
            dev.host.run(
                f"ethtool -G {dev.name} "
                + " ".join(
                    ring_cfg_name + " " + str(ring_cfg_value)
                    for ring_cfg_name, ring_cfg_value in original_config.items()
                    if ring_cfg_name in configured_config
                )
            )

        super().hw_deconfig(config)

    def describe_hw_config(self, config):
        desc = super().describe_hw_config(config)

        # Describe ring configuration
        dev_ring_config_config = config.hw_config.get("dev_ring_config", {})
        if dev_ring_config_config:
            desc += [
                f"{device.host.hostid} device {device.name} ring configuration: "
                + " ".join(
                    ring_cfg_name + " " + str(ring_cfg_value)
                    for ring_cfg_name, ring_cfg_value in dev_ring_config[
                        "configured"
                    ].items()
                )
                for device, dev_ring_config in dev_ring_config_config.items()
            ]
        else:
            desc += ["device ring configuration skipped"]

        return desc


def process_ring_settings_output(output, configured_keys):
    # $ ethtool --json -g enp0s31f6
    # [ {
    #         "ifname": "enp0s31f6",
    #         "rx-max": 4096,
    #         "tx-max": 4096,
    #         "rx": 256,
    #         "tx": 256,
    #         "tx-push": false,
    #         "rx-push": false
    # } ]

    output = loads(output)[0]  # just single inf
    result = {}
    for key in configured_keys:
        result[key] = output[key]

    return result
