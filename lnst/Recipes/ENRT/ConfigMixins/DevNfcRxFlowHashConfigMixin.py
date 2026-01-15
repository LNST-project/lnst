import re
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
        xfrm_original_config = hw_config["xfrm_original"] = {}

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
                    self._disable_xfrm_transformations(xfrm_original_config, device)

                device.host.run(
                    f"ethtool -N {device.name} rx-flow-hash {protocol} {protocol_setting}"
                )

                nfc_config[device][protocol]["configured"] = "".join(sorted([*protocol_setting]))

    def _disable_xfrm_transformations(self, xfrm_original_config, device):
        xfrm_ethtool_job = device.host.run(f"ethtool -x {device.name}")
        xfrm_original_config[device] = process_xfrm_output(xfrm_ethtool_job.stdout)

        if not xfrm_original_config[device]:
            # if no xfrm values are parsed, this is not supported so no need to
            # do more configuration
            return

        device.host.run(
            f"ethtool -X {device.name} xfrm none"
        )

    def hw_deconfig(self, config):
        nfc_config = config.hw_config.get("dev_nfc_rx_flow_hash_configuration", {})
        for dev, dev_nfc in nfc_config.items():
            for protocol, protocol_setting in dev_nfc.items():
                if protocol_setting['original']:
                    dev.host.run(
                        f"ethtool -N {dev.name} rx-flow-hash {protocol} {protocol_setting['original']}"
                    )
                else:
                    logging.warning(f"rx-flow-hash protocol setting is empty for {dev.host.hostid} {dev.name}, skipping deconfig")

        xfrm_original_config = config.hw_config.get("xfrm_original", {})
        for device, xfrm_dev_config in xfrm_original_config.items():
            if not any(i == "on" for i in xfrm_dev_config.values()):
                continue

            # this sets the xfrm bitmap to 0 and sets the individual bits to 1
            # based on original state
            dev.host.run(f"ethtool -X {device.name} xfrm none " +
                 " ".join(
                     "xfrm " + i[0]
                     for i in xfrm_dev_config.items()
                     if i[1] == "on"
                 )
            )

        if xfrm_original_config:
            del config.hw_config["xfrm_original"]

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
    "L2DA": "m",
    "L3 proto": "t",
    "VLAN tag": "v",
}

def process_nfc_output(output):
    result = []

    for line in output.split("\n")[1:]:
        if not line:
            continue

        try:
            result.append(nfc_rx_flow_hash_mapping[line])
        except KeyError:
            logging.warning(f"Unknown input from nfc rx-flow-hash: {line}")
            continue

    return "".join(sorted(result))

def process_xfrm_output(output):
    result = {}
    started = False

    for line in output.split("\n")[1:]:
        if not line:
            continue
        if line == "RSS input transformation:":
            # parsing all values under this section
            started = True
            continue

        if started and line[0] != ' ':
            # all values need to start with empty spaces
            # if there's another section starting it will start from the first character
            break

        if not started:
            continue

        if m := re.match(r"\s*(\S*): (on|off)", line):
            result[m.group(1)] = m.group(2)

    return result
