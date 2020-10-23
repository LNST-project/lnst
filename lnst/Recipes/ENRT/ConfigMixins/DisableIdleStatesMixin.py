from lnst.Common.Parameters import IntParam
from lnst.Recipes.ENRT.ConfigMixins import BaseSubConfigMixin

class DisableIdleStatesMixin(BaseSubConfigMixin):
    """
    This mixin class is an extension to the :any:`BaseEnrtRecipe` class that can
    be used to control the CPU idle states before running the tests.

    Any recipe that wants to use the mixin must define the
    :attr:`disable_idlestates_host_list` property first.

    :param minimal_idlestates_latency:
        (optional test parameter) an integer, the value is passed as the latency
        argument of the **'cpupower idle-set -D'** command that will disable
        all idle states with an equal or higher latency than the specified value
        on all hosts defined by :attr:`disable_idlestates_host_list` property.
        If the value is 0 this will effectively disable all CPU idle states.
    """

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
