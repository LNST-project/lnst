import re

from lnst.Common.Parameters import DictParam
from lnst.Recipes.ENRT.ConfigMixins.BaseHWConfigMixin import BaseHWConfigMixin

class DevRxHashFunctionConfigMixin(BaseHWConfigMixin):
    #TODO: add docs
    dev_rx_hash_functions = DictParam(mandatory=False)

    def hw_config(self, config):
        super().hw_config(config)

        if not self.params.get("dev_rx_hash_functions"):
            return

        hw_config = config.hw_config
        rx_hash_func_config = hw_config["dev_rx_hash_function_configuration"] = {}

        device_settings = self._parse_device_settings(self.params.dev_rx_hash_functions)
        for device, rx_hash_function in device_settings.items():
            # TODO: handle netlink error: Operation not supported
            ethtool_job = device.host.run(f"ethtool -x {device.name}")
            original_hash_func = process_hash_func_output(ethtool_job.stdout)

            rx_hash_func_config[device] = {
                "original": original_hash_func,
            }

            device.host.run(
                f"ethtool -X {device.name} hfunc {rx_hash_function}"
            )

            rx_hash_func_config[device]["configured"] = rx_hash_function

    def hw_deconfig(self, config):
        rx_hash_func_config = config.hw_config.get("dev_rx_hash_function_configuration", {})
        for dev, dev_hash_func_config in rx_hash_func_config.items():
            dev.host.run(
                f"ethtool -X {dev.name} hfunc {dev_hash_func_config['original']}"
            )

        super().hw_deconfig(config)

    def describe_hw_config(self, config):
        desc = super().describe_hw_config(config)

        rx_hash_func_config = config.hw_config.get("dev_rx_hash_function_configuration", {})

        if rx_hash_func_config:
            desc += [
                f"{device.host.hostid} device {device.name} rx hash function configured: {dev_hash_func_config['configured']}"
                for device, dev_hash_func_config in rx_hash_func_config.items()
            ]
        else:
            desc += ["rx hash function configuration skipped"]

        return desc


def process_hash_func_output(output):
    regex = re.compile(r".*(toeplitz|xor|crc): (on|off).*")

    for line in output.split("\n")[1:]:
        if not line:
            continue

        if match := regex.match(line):
            hash_func, state = match.groups()
            if state == 'on':
                return hash_func

    raise Exception("Could not find rx hash function")
