from lnst.Common.Parameters import DictParam
from lnst.Recipes.ENRT.ConfigMixins.BaseHWConfigMixin import BaseHWConfigMixin


class DevQueuesConfigMixin(BaseHWConfigMixin):
    dev_queues = DictParam(mandatory=False)
    dev_queue_sizes = DictParam(mandatory=False)

    def hw_config(self, config):
        super().hw_config(config)

        hw_config = config.hw_config

        if self.params.get("dev_queues"):
            hw_config["dev_queues"] = {}
            self._configure_queue_counts(hw_config)

        if self.params.get("dev_queue_sizes"):
            hw_config["dev_queue_sizes"] = {}
            self._configure_queue_sizes(hw_config)

    def _configure_queue_counts(self, hw_config):
        device_settings = self._parse_device_settings(self.params.dev_queues)
        for device, dev_queues in device_settings.items():
            # TODO: handle netlink error: Operation not supported
            ethtool_job = device.host.run(f"ethtool -l {device.name}")
            original_queues = process_queues_output(ethtool_job.stdout)

            hw_config["dev_queues"][device] = {
                "original": original_queues["current"],
            }

            device.host.run(
                f"ethtool -L {device.name} "
                + " ".join(
                    queue_name + " " + str(queue_setting)
                    for queue_name, queue_setting in dev_queues.items()
                )
            )

            hw_config["dev_queues"][device]["configured"] = dev_queues

    def _configure_queue_sizes(self, hw_config):
        device_settings = self._parse_device_settings(self.params.dev_queue_sizes)
        for device, queue_sizes in device_settings.items():
            # Get original queue sizes
            ethtool_job = device.host.run(f"ethtool -g {device.name}")
            original_sizes = process_queue_sizes_output(ethtool_job.stdout)

            hw_config["dev_queue_sizes"][device] = {
                "original": original_sizes["current"],
            }

            # Set new queue sizes
            device.host.run(
                f"ethtool -G {device.name} "
                + " ".join(
                    queue_name + " " + str(size_setting)
                    for queue_name, size_setting in queue_sizes.items()
                )
            )

            hw_config["dev_queue_sizes"][device]["configured"] = queue_sizes

    def hw_deconfig(self, config):
        # Restore queue counts
        dev_queues_config = config.hw_config.get("dev_queues", {})
        for dev, dev_queues in dev_queues_config.items():
            configured_queues = dev_queues.get("configured", {})
            original_queues = dev_queues.get("original", {})
            dev.host.run(
                f"ethtool -L {dev.name} "
                + " ".join(
                    queue_name + " " + str(queue_setting)
                    for queue_name, queue_setting in original_queues.items()
                    if queue_name in configured_queues
                )
            )

        # Restore queue sizes
        dev_queue_sizes_config = config.hw_config.get("dev_queue_sizes", {})
        for dev, dev_queue_sizes in dev_queue_sizes_config.items():
            configured_sizes = dev_queue_sizes.get("configured", {})
            original_sizes = dev_queue_sizes.get("original", {})
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

        # Describe queue count configuration
        dev_queues_config = config.hw_config.get("dev_queues", {})
        if dev_queues_config:
            desc += [
                f"{device.host.hostid} device {device.name} queues configured: "
                + " ".join(
                    queue_name + " " + str(queue_setting)
                    for queue_name, queue_setting in dev_queues["configured"].items()
                )
                for device, dev_queues in dev_queues_config.items()
            ]
        else:
            desc += ["device queues configuration skipped"]

        # Describe queue size configuration
        dev_queue_sizes_config = config.hw_config.get("dev_queue_sizes", {})
        if dev_queue_sizes_config:
            desc += [
                f"{device.host.hostid} device {device.name} queue sizes configured: "
                + " ".join(
                    queue_name + " " + str(size_setting)
                    for queue_name, size_setting in dev_queue_sizes["configured"].items()
                )
                for device, dev_queue_sizes in dev_queue_sizes_config.items()
            ]
        else:
            desc += ["device queue sizes configuration skipped"]

        return desc


def process_queues_output(output):
    # format of ethtool -l:
    #
    # Channel parameters for ens7f0:
    # Pre-set maximums:
    # RX:		n/a
    # TX:		n/a
    # Other:		n/a
    # Combined:	32
    # Current hardware settings:
    # RX:		n/a
    # TX:		n/a
    # Other:		n/a
    # Combined:	16

    result = {
        "preset": {},
        "current": {},
    }

    key = None
    for line in output.split("\n")[1:]:
        if not line:
            continue

        if line == "Pre-set maximums:":
            key = "preset"
        elif line == "Current hardware settings:":
            key = "current"
        else:
            queue_name, queue_setting = line.split(":")
            queue_name = queue_name.lower()
            queue_setting = queue_setting.strip()
            if queue_setting == "n/a":
                queue_setting = None

            result[key][queue_name] = queue_setting

    return result


def process_queue_sizes_output(output):
    # format of ethtool -g:
    #
    # Ring parameters for ens7f0:
    # Pre-set maximums:
    # RX:		4096
    # RX Mini:	0
    # RX Jumbo:	0
    # TX:		4096
    # Current hardware settings:
    # RX:		1024
    # RX Mini:	0
    # RX Jumbo:	0
    # TX:		1024

    result = {
        "preset": {},
        "current": {},
    }

    key = None
    for line in output.split("\n")[1:]:
        if not line:
            continue

        if line == "Pre-set maximums:":
            key = "preset"
        elif line == "Current hardware settings:":
            key = "current"
        else:
            parts = line.split(":")
            if len(parts) < 2:
                continue
                
            queue_name, queue_setting = parts[0], parts[1]
            queue_name = queue_name.lower().strip()
            queue_setting = queue_setting.strip()
            try:
                queue_setting = int(queue_setting)
            except ValueError:
                queue_setting = 0

            result[key][queue_name] = queue_setting

    return result
