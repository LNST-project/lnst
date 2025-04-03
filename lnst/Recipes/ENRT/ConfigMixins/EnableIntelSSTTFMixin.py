import re

from lnst.Common.LnstError import LnstError
from lnst.Common.Parameters import BoolParam
from lnst.Controller.RecipeResults import ResultLevel, ResultType
from lnst.Recipes.ENRT.ConfigMixins import BaseSubConfigMixin


class EnableIntelSSTTFMixin(BaseSubConfigMixin):
    enable_intel_sst_tf = BoolParam(default=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if getattr(self.params, "disable_turboboost", True):
            raise ValueError(
                "turboboost needs to be enabled when enabling intel_sst. "
                f"intel_sst just allows higher clock speed for turbo boost."
            )

    @property
    def intel_sst_tf_host_list(self):
        """
        The value of this property is a list of hosts for which the intel
        SST-TF should be turned on. Derived class can override this property.
        """
        return self.matched

    def _is_sst_supported(self, host):

        sst_info = host.run("intel-speed-select --info", job_level=ResultLevel.DEBUG)

        result = sst_info.passed
        if not re.search(
            r"Intel\(R\) SST-TF \(feature turbo-freq\) is supported", sst_info.stderr
        ):
            result = ResultType.FAIL

        return result

    def _system_cpus(self, host):
        job = host.run(
            "cat /proc/cpuinfo | grep -E '^processor' | cut -d':' -f2 | tr -d ' '"
        )
        if not job.passed:
            raise LnstError("Could not get system cpus.")

        return ",".join(cpu.strip() for cpu in job.stdout.splitlines())

    def _ssted_cpus(self):
        cpus = []
        if "perf_tool_cpu" in self.params:
            cpus.extend(self.params.perf_tool_cpu)

        if "dev_intr_cpu" in self.params:
            cpus.extend(self.params.dev_intr_cpu)

        # TODO: multi dev intr config mixin support

        return ",".join(str(cpu) for cpu in cpus)

    def apply_sub_configuration(self, config):
        super().apply_sub_configuration(config)

        if not self.params.enable_intel_sst_tf:
            return

        for host in self.intel_sst_tf_host_list:
            if not self._is_sst_supported(host):
                raise LnstError(f"Machine {host} doesn't support Intel SST-TF.")

            idlestates = host.run("cpupower idle-set -E")
            if not idlestates.passed:
                raise LnstError("Could not enable all idle states.")

            reset_tf_settings = host.run(
                f"intel-speed-select -c {self._system_cpus(host)} turbo-freq disable –auto"
            )
            if not reset_tf_settings.passed:
                raise LnstError("Could not reset previous sst-tf settings.")

            set_tf = host.run(
                f"intel-speed-select -c {self._ssted_cpus()} turbo-freq enable –auto"
            )
            if not set_tf.passed:
                raise LnstError(f"Could not enable sst-tf for {self._ssted_cpus()}")

    def generate_sub_configuration_description(self, config):
        description = super().generate_sub_configuration_description(config)

        if self.params.enable_intel_sst_tf:
            for host in self.intel_sst_tf_host_list:
                description.append(
                    f"intel sst-tf enabled on {host} cpus: {self._ssted_cpus()}"
                )
        else:
            description.append(
                "configuration of turboboost through intel_pstate skipped"
            )

        return description

    def remove_sub_configuration(self, config):
        if not self.params.enable_intel_sst_tf:
            return

        for host in self.intel_sst_tf_host_list:
            pass  # TODO

        return super().remove_sub_configuration(config)
