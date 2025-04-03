import re
import logging

from lnst.Common.Utils import is_installed
from lnst.Common.Parameters import BoolParam
from lnst.Controller.Recipe import RecipeError
from lnst.Controller.RecipeResults import ResultLevel
from lnst.Recipes.ENRT.ConfigMixins import BaseSubConfigMixin


class EnableIntelSSTTFMixin(BaseSubConfigMixin):
    TURBO_PATH = "/sys/devices/system/cpu/intel_pstate/no_turbo"

    enable_intel_sst_tf = BoolParam()

    @property
    def intel_sst_tf_host_list(self):
        """
        The value of this property is a list of hosts for which the intel
        SST-TF should be turned on. Derived class can override this property.
        """
        return self.matched

    def apply_sub_configuration(self, config):
        super().apply_sub_configuration(config)

        if getattr(self.params, "enable_intel_sst_tf", None) is None:
            return

        for host in self.intel_sst_tf_host_list:
            if not self._is_sst_supported(host):
                raise RecipeError(f"Machine {host} doesn't support Intel SST-TF.")

            if not host.run("cpupower idle-set -E").passed:
                raise RecipeError("Could not enable all idle states.")

            reset_tf_settings = host.run(
                f"intel-speed-select -c {self._system_cpus(host)} turbo-freq disable –auto"
            )
            if not reset_tf_settings.passed:
                raise RecipeError("Could not reset previous sst-tf settings.")

            set_tf = host.run(
                f"intel-speed-select -c {self._ssted_cpus()} turbo-freq enable –auto"
            )
            if not set_tf.passed:
                raise RecipeError(f"Could not enable sst-tf for {self._ssted_cpus()}")

    def remove_sub_configuration(self, config):
        if getattr(self.params, "enable_intel_sst_tf", None) is None:
            return super().remove_sub_configuration(config)

        logging.warning(
            "Deconfiguration doesn't work right now. It's a bug in "
            "intel-speed-select. To deconfigure, reboot the machine..."
        )

        for host in self.intel_sst_tf_host_list:
            if not host.run("intel-speed-select turbo-freq disable").passed:
                logging.warning(
                    f"Could not remove intel sst-tf configuration on {host}"
                )

        return super().remove_sub_configuration(config)

    def generate_sub_configuration_description(self, config):
        description = super().generate_sub_configuration_description(config)

        if getattr(self.params, "enable_intel_sst_tf", None) is not None:
            for host in self.intel_sst_tf_host_list:
                description.append(
                    f"intel sst-tf enabled on {host} cpus: {self._ssted_cpus()}"
                )
        else:
            description.append("configuration of intel_sst-tf skipped")

        return description

    def _is_sst_supported(self, host):
        if not is_installed("intel-speed-select"):
            raise RecipeError("intel-speed-select is not installed.")

        file_check = host.run(f"ls {self.TURBO_PATH}", job_level=ResultLevel.DEBUG)
        if not file_check.passed:
            raise RecipeError(
                "intel-speed-select is not supported." "Not even TurboBoost is"
            )

        tb_check = host.run(f"cat {self.TURBO_PATH}", job_level=ResultLevel.DEBUG)
        if not tb_check.passed or tb_check.stdout != "0\n":
            raise RecipeError("Intel SST-TF requires TurboBoost to be enabled.")

        sst_info = host.run("intel-speed-select --info", job_level=ResultLevel.DEBUG)

        if not re.search(
            r"Intel\(R\) SST-TF \(feature turbo-freq\) is supported", sst_info.stderr
        ):
            return False

        return True

    def _system_cpus(self, host):
        job = host.run(
            "cat /proc/cpuinfo | grep -E '^processor' | cut -d':' -f2 | tr -d ' '"
        )
        if not job.passed:
            raise RecipeError("Could not get system cpus.")

        return ",".join(cpu.strip() for cpu in job.stdout.splitlines())

    def _ssted_cpus(self):
        cpus = set()
        cpus.update(self.params.get("perf_tool_cpu", []))
        cpus.update(self.params.get("dev_intr_cpu", []))

        # TODO: multi dev intr config mixin support

        return ",".join(str(cpu) for cpu in cpus)
