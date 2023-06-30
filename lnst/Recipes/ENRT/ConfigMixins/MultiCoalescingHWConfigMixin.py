from copy import copy

from lnst.Common.Parameters import DictParam
from lnst.Recipes.ENRT.ConfigMixins.BaseHWConfigMixin import BaseHWConfigMixin


class MultiCoalescingHWConfigMixin(BaseHWConfigMixin):
    """
    This class is an extension to the :any:`BaseEnrtRecipe` class that enables
    interrupt coalescing configuration on the devices defined by
    :attr:`coalescing_hw_config_dev_list` property.

    This mixin is a "multi device" variant of the :any:`CoalescingHWConfigMixin`
    and allows configuration of individual devices instead of sharing the same
    configuration. This may be required when different interrupt coalescing is
    required by a flow generator and receiver host.

    :param coalescing_settings:
        (optional test parameter) dictionary to specify coalescing settings
        for individual devices, in 'ethtool -C ...' format
    """
    coalescing_settings = DictParam(mandatory=False, default={})

    def hw_config(self, config):
        super().hw_config(config)

        device_settings = self._parse_device_settings(self.params.coalescing_settings)
        for device, device_setting in device_settings.items():
            device_setting_copy = copy(device_setting)
            # first, fetch adaptive setting as it needs to be turned off before
            # configuring individual coalescing settings
            for param in ["adaptive-tx", "adaptive-rx"]:
                if param_value := device_setting_copy.pop(param, None):
                    self._configure_dev_attribute(
                        config,
                        [device],
                        coalescing_param_to_device_attribute(param),
                        param_value == "on",
                    )

            for param, param_value in device_setting_copy.items():
                self._configure_dev_attribute(
                    config,
                    [device],
                    coalescing_param_to_device_attribute(param),
                    param_value,
                )

    def hw_deconfig(self, config):
        device_settings = self._parse_device_settings(self.params.coalescing_settings)
        for device, device_setting in device_settings.items():
            device_setting_copy = copy(device_setting)
            for param in device_setting:
                if param in ["adaptive-tx", "adaptive-rx"]:
                    continue
                device_setting_copy.pop(param)
                self._deconfigure_dev_attribute(
                    config,
                    [device],
                    coalescing_param_to_device_attribute(param),
                )

            for param in device_setting_copy:
                self._deconfigure_dev_attribute(
                    config,
                    [device],
                    coalescing_param_to_device_attribute(param),
                )

        super().hw_deconfig(config)

    def describe_hw_config(self, config):
        desc = super().describe_hw_config(config)

        device_settings = self._parse_device_settings(self.params.coalescing_settings)
        coalescing_attrs = {
            coalescing_param_to_device_attribute(key)
            for setting in device_settings.values()
            for key in setting.keys()
        }
        for attr in sorted(coalescing_attrs):
            desc.extend(
                self._describe_dev_attribute(
                    config,
                    attr,
                )
            )

        return desc


def coalescing_param_to_device_attribute(param):
    """
    This mixin accepts the coalesce_settings keys in 'ethtool -C' format
    The Device class uses more descriptive property names along with
    underscores, so we need to translate the keys to property names
    """
    if param in ["adaptive-tx", "adaptive-rx"]:
        return param.replace("-", "_") + "_coalescing"

    return "coalescing_" + param.replace("-", "_")
