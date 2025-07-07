import logging

from lnst.Common.Parameters import DictParam
from lnst.Recipes.ENRT.ConfigMixins.BaseHWConfigMixin import BaseHWConfigMixin


class DevNfcRxFlowHashConfigMixin(BaseHWConfigMixin):
    dev_nfc_rx_flow_hash_config = DictParam(mandatory=False)

    def hw_config(self, config):
        super().hw_config(config)

        if not self.params.get("dev_nfc_rx_flow_hash_config"):
            return

        hw_config = config.hw_config
        nfc_config = hw_config["dev_nfc_rx_flow_hash_configuration"] = {}

        device_settings = self._parse_device_settings(self.params.dev_nfc_rx_flow_hash_config)
        for device, nfc_rx_flow_hash_config in device_settings.items():
            nfc_config[device] = {}
            for protocol, protocol_setting in nfc_rx_flow_hash_config.items():
                # TODO: handle netlink error: Operation not supported
                ethtool_job = device.host.run(f"ethtool -n {device.name} rx-flow-hash {protocol}")
                original_flow_hash = process_nfc_output(ethtool_job.stdout)

                nfc_config[device][protocol] = {
                    "original": original_flow_hash,
                }

                if protocol_setting not in {"sd", "fn", "sdfn"}:
                    logging.info(
                        f"Selected protocol setting {protocol_setting} requires disabling symmetric hashing: setting xfrm none"
                    )
                    device.host.run(
                        f"ethtool -X {device.name} xfrm none"
                    )

                device.host.run(
                    f"ethtool -N {device.name} rx-flow-hash {protocol} {protocol_setting}"
                )

                nfc_config[device][protocol]["configured"] = "".join(sorted([*protocol_setting]))

    def hw_deconfig(self, config):
        nfc_config = config.hw_config.get("dev_nfc_rx_flow_hash_configuration", {})
        for dev, dev_nfc in nfc_config.items():
            for protocol, protocol_setting in dev_nfc.items():
                dev.host.run(
                    f"ethtool -N {dev.name} rx-flow-hash {protocol} {protocol_setting['original']}"
                )

        super().hw_deconfig(config)

    def describe_hw_config(self, config):
        desc = super().describe_hw_config(config)

        nfc_config = config.hw_config.get("dev_nfc_rx_flow_hash_configuration", {})
        if nfc_config:
            desc += [
                f"{device.host.hostid} device {device.name} nfc rx-flow-hash {protocol} configured: {protocol_setting['configured']}"
                for device, dev_nfc in nfc_config.items()
                for protocol, protocol_setting in dev_nfc.items()
            ]
        else:
            desc += ["nfc rx-flow-hash not configured"]

        return desc


nfc_rx_flow_hash_mapping = {
    "IP SA": "s",
    "IP DA": "d",
    "L4 bytes 0 & 1 [TCP/UDP src port]": "f",
    "L4 bytes 2 & 3 [TCP/UDP dst port]": "n",
}

def process_nfc_output(output):
    result = []

    for line in output.split("\n")[1:]:
        if not line:
            continue

        try:
            result.append(nfc_rx_flow_hash_mapping[line])
        except KeyError:
            raise Exception(f"Unknown input from nfc rx-flow-hash: {line}")

    return "".join(sorted(result))
