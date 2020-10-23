from lnst.Common.Parameters import BoolParam
from lnst.Controller.RecipeResults import ResultLevel
from lnst.Recipes.ENRT.ConfigMixins import BaseSubConfigMixin

class DisableTurboboostMixin(BaseSubConfigMixin):
    disable_turboboost = BoolParam(default=False)

    @property
    def disable_turboboost_host_list(self):
        """
        The value of this property is a list of hosts for which the CPU turboboost
        should be turned off. Derived class can override this property.
        """
        return []

    def _is_turboboost_supported(self, host):
        file_check = host.run(
                "ls /sys/devices/system/cpu/intel_pstate/no_turbo",
                job_level=ResultLevel.DEBUG)
        return file_check.passed

    def apply_sub_configuration(self, config):
        super().apply_sub_configuration(config)

        if self.params.disable_turboboost:
            for host in self.disable_turboboost_host_list:
                if self._is_turboboost_supported(host):
                    # TODO: save previous state
                    host.run("echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo")

    def generate_sub_configuration_description(self, config):
        description = super().generate_sub_configuration_description(config)

        if self.params.disable_turboboost:
            for host in self.disable_turboboost_host_list:
                if self._is_turboboost_supported(host):
                    description.append("turboboost disabled through intel_pstate on {}".format(host.hostid))
                else:
                    description.append("warning: user requested to disable turboboost "\
                            "through intel_pstate but the sysfs file is not available "\
                            "on host {}".format(host.hostid))
        else:
            description.append("configuration of turboboost through intel_pstate skipped")

        return description

    def remove_sub_configuration(self, config):
        if self.params.disable_turboboost:
            for host in self.disable_turboboost_host_list:
                if self._is_turboboost_supported(host):
                    # TODO: restore previous state
                    host.run("echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo")

        return super().remove_sub_configuration(config)
