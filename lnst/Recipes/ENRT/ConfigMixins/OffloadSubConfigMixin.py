import copy

from lnst.Common.Parameters import Param
from lnst.Controller.RecipeResults import ResultLevel
from lnst.Recipes.ENRT.ConfigMixins.BaseSubConfigMixin import BaseSubConfigMixin


class OffloadSubConfigMixin(BaseSubConfigMixin):
    """
    This class is an extension to the :any:`BaseEnrtRecipe` class that enables
    offload configuration on the devices defined by :attr:`offload_nics`.

    :param offload_combinations:
        (optional test parameter) defines the offload features to be enabled
        or disabled on the devices
    """

    offload_combinations = Param(
        default=(dict(gro="on", gso="on", tso="on", tx="on", rx="on"),)
    )

    @property
    def offload_nics(self):
        """
        The value of this property is a list of devices for which the offload
        settings should be configured. It has to be defined by a derived class.
        """
        raise NotImplementedError("Subclass must implement this property")

    def generate_sub_configurations(self, config):
        for parent_config in super().generate_sub_configurations(config):
            if not self.params.offload_combinations:
                yield parent_config

            for offload_settings in self.params.offload_combinations:
                new_config = copy.copy(config)
                new_config.offload_settings = offload_settings

                yield new_config

    def apply_sub_configuration(self, config):
        super().apply_sub_configuration(config)

        offload_settings = getattr(config, "offload_settings", None)
        if offload_settings:
            ethtool_offload_string = ""
            for name, value in list(offload_settings.items()):
                ethtool_offload_string += " %s %s" % (name, value)

            for nic in self.offload_nics:
                nic.netns.run(
                    "ethtool -K {} {}".format(nic.name, ethtool_offload_string),
                    job_level=ResultLevel.NORMAL,
                )

    def generate_sub_configuration_description(self, config):
        description = super().generate_sub_configuration_description(config)
        if getattr(config, "offload_settings", None):
            description.append(
                "Currently configured offload combination: {}".format(
                    " ".join(
                        [
                            "{}={}".format(k, v)
                            for k, v in config.offload_settings.items()
                        ]
                    )
                )
            )
        else:
            description.append("NIC offload configuration skipped")

        return description

    def remove_sub_configuration(self, config):
        offload_settings = getattr(config, "offload_settings", None)
        if offload_settings:
            ethtool_offload_string = ""
            for name, value in list(offload_settings.items()):
                ethtool_offload_string += " %s %s" % (name, "on")

            for nic in self.offload_nics:
                # set all the offloads back to 'on' state
                nic.netns.run(
                    "ethtool -K {} {}".format(nic.name, ethtool_offload_string),
                    job_level=ResultLevel.NORMAL,
                )

        return super().remove_sub_configuration(config)

    def generate_flow_combinations(self, config):
        for flows in super().generate_flow_combinations(config):
            if self._check_test_offload_conflicts(config, flows):
                # TODO log skip
                continue
            else:
                yield flows

    def _check_test_offload_conflicts(self, config, flows):
        for flow in flows:
            if (
                flow.type == "udp_stream"
                and config.offload_settings.get("gro", "on") == "off"
            ):
                return True
            elif (
                flow.type == "sctp_stream"
                and "off" in config.offload_settings.values()
                and config.offload_settings.get("gso", "on") == "on"
            ):
                return True
        return False
