from lnst.Common.Parameters import IntParam
from lnst.Recipes.ENRT.ConfigMixins import BaseSubConfigMixin

class DisableIdleStatesMixin(BaseSubConfigMixin):
    minimal_idlestates_latency = IntParam()

    @property
    def disable_idlestates_host_list(self):
        """
        The value of this property is a list of hosts for which the CPU idle
        states should be turned off. Derived class can override this property.
        """
        return []

    def apply_sub_configuration(self, config):
        super().apply_sub_configuration(config)

        latency = getattr(self.params, "minimal_idlestates_latency", None)
        if latency is not None:
            for host in self.disable_idlestates_host_list:
                # TODO: save previous state
                host.run("cpupower idle-set -D {}".format(latency))

    def generate_sub_configuration_description(self, config):
        description = super().generate_sub_configuration_description(config)

        latency = getattr(self.params, "minimal_idlestates_latency", None)
        if latency is not None:
            for host in self.disable_idlestates_host_list:
                description.append("disabled idle states with latency higher than "\
                        "{} on host {}".format(latency, host.hostid)
                        )
        else:
            description.append("configuration of idle states skipped")

        return description

    def remove_sub_configuration(self, config):
        for host in self.disable_idlestates_host_list:
            host.run("cpupower idle-set -E")

        return super().remove_sub_configuration(config)
