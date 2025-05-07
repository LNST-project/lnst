from json import loads
from lnst.Common.Parameters import DictParam
from lnst.Recipes.ENRT.ConfigMixins.BaseHWConfigMixin import BaseHWConfigMixin


class DevRingConfigMixin(BaseHWConfigMixin):
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
            # Get original queue sizes
            ethtool_job = device.host.run(f"ethtool --json -g {device.name}")
            original_sizes = process_queue_sizes_output(
                ethtool_job.stdout, [configured for configured in ring_configs.keys()]
            )

            hw_config["dev_ring_config"][device] = {
                "original": original_sizes,
            }

            # Set new queue sizes
            device.host.run(
                f"ethtool -G {device.name} "
                + " ".join(
                    queue_name + " " + str(size_setting)
                    for queue_name, size_setting in ring_configs.items()
                )
            )

            hw_config["dev_ring_config"][device]["configured"] = ring_configs

    def hw_deconfig(self, config):
        # Restore queue sizes
        dev_ring_config = config.hw_config.get("dev_ring_config", {})
        for dev, dev_ring_config in dev_ring_config.items():
            configured_sizes = dev_ring_config.get("configured", {})
            original_sizes = dev_ring_config.get("original", {})
            dev.host.run(
                f"ethtool -G {dev.name} "
                + " ".join(
                    queue_name + " " + str(size_setting)
                    for queue_name, size_setting in original_sizes.items()
                    if queue_name in configured_sizes
                )
            )

        super().hw_deconfig(config)

    def describe_hw_config(self, config):
        desc = super().describe_hw_config(config)

        # Describe queue size configuration
        dev_ring_config_config = config.hw_config.get("dev_ring_config", {})
        if dev_ring_config_config:
            desc += [
                f"{device.host.hostid} device {device.name} queue sizes configured: "
                + " ".join(
                    queue_name + " " + str(size_setting)
                    for queue_name, size_setting in dev_ring_config[
                        "configured"
                    ].items()
                )
                for device, dev_ring_config in dev_ring_config_config.items()
            ]
        else:
            desc += ["device queue sizes configuration skipped"]

        return desc


def process_queue_sizes_output(output, configured_values):
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
    for configured in configured_values:
        result[configured] = output[configured]

    return result
