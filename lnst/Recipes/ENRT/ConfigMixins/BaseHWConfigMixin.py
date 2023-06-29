from lnst.Recipes.ENRT.ConfigMixins.BaseSubConfigMixin import BaseSubConfigMixin

class BaseHWConfigMixin(BaseSubConfigMixin):
    def apply_sub_configuration(self, config):
        super().apply_sub_configuration(config)
        self.hw_config(config)

    def remove_sub_configuration(self, config):
        self.hw_deconfig(config)
        return super().remove_sub_configuration(config)

    def generate_sub_configuration_description(self, config):
        desc = super().generate_sub_configuration_description(config)
        desc.extend(self.describe_hw_config(config))
        return desc

    def hw_config(self, config):
        config.hw_config = {}

    def hw_deconfig(self, config):
        del config.hw_config

    def describe_hw_config(self, config):
        return []

    def _configure_dev_attribute(self, config, dev_list, attr_name, value):
        hw_config = config.hw_config
        if len(dev_list) > 0:
            attr_cfg = hw_config.setdefault(attr_name + "_configuration", {})

        for dev in dev_list:
            attr_cfg[dev] = {}
            attr_cfg[dev]["original"] = getattr(dev, attr_name)
            setattr(dev, attr_name, value)
            attr_cfg[dev]["configured"] = getattr(dev, attr_name)

    def _deconfigure_dev_attribute(self, config, dev_list, attr_name):
        hw_config = config.hw_config

        try:
            attr_cfg = hw_config[attr_name + "_configuration"]
        except KeyError:
            return

        for dev in dev_list:
            value = attr_cfg[dev]["original"]
            setattr(dev, attr_name, value)
            del attr_cfg[dev]

    def _describe_dev_attribute(self, config, attr_name):
        hw_config = config.hw_config
        res = []
        try:
            attr = hw_config[attr_name + "_configuration"]
        except:
            res.append("{} configuration skipped.".format(attr_name))
            return res

        for dev, info in attr.items():
            res.append(
                "{}.{}.{} configured to {}, original value {}".format(
                    dev.host.hostid,
                    dev.name,
                    attr_name,
                    info["configured"],
                    info["original"],
                )
            )

        return res

    def _parse_device_settings(self, settings={}):
        """
        This method can be used to transform the individual device configurations
        specified through recipe parameters into mapping of device instance to
        device specific configiuration.

        This is typical for multi-device config mixins such as DevQueuesConfigMixin.

        The method expects that mixins use following common format of the recipe
        parameter for the devices configuration:
        {
            "host1": {
                "eth1": device_specific_config1 # can be any type, depends on the mixin implementation
            },
            "host2": {
                "eth1": device_specific_config2 # can be any type, depends on the mixin implementation
            }
        }

        The first level keys in the dictionary are the host ids defined through
        the `HostReq`s in individual recipes.
        The second level keys are device ids defined through `DeviceReq` in
        individual recipes.

        The method returns a dictionary where resolved device `DeviceReq`s are
        mapped to device_specific_configs.
        """
        result_mapping = {}
        for host in settings:
            try:
                matched_host = getattr(self.matched, host)
            except AttributeError:
                raise Exception(
                    f"Host {host} not found in matched hosts, while parsing {settings}"
                )

            for device, device_setting in settings[host].items():
                try:
                    matched_device = getattr(matched_host, device)
                except AttributeError:
                    raise Exception(
                        f"Device {device} not found on {host}, while parsing {settings}"
                    )

                if matched_device not in result_mapping:
                    result_mapping[matched_device] = device_setting
                else:
                    raise Exception(
                        f"Device host {host} device {device} specified multiple times"
                    )

        return result_mapping
