import re

from lnst.Common.Parameters import ListParam
from lnst.Controller.Recipe import RecipeError
from lnst.Controller.RecipeResults import ResultLevel
from lnst.Recipes.ENRT.ConfigMixins.BaseHWConfigMixin import BaseHWConfigMixin


class DevInterruptHWConfigMixin(BaseHWConfigMixin):
    """
    This class is an extension to the :any:`BaseEnrtRecipe` class that enables
    the CPU affinity (CPU pinning) of the test device IRQs. The test devices
    are defined by :attr:`dev_interrupt_hw_config_dev_list` property.

     .. note::
        Note that this Mixin also stops the irqbalance service.

    :param dev_intr_cpu:
        (optional test parameter) CPU ids to which the device IRQs should be pinned
    """

    dev_intr_cpu = ListParam(mandatory=False)

    @property
    def dev_interrupt_hw_config_dev_list(self):
        """
        The value of this property is a list of devices for which the IRQ CPU
        affinity should be configured. It has to be defined by a derived class.
        """
        return []

    def hw_config(self, config):
        super().hw_config(config)

        hw_config = config.hw_config

        if "dev_intr_cpu" in self.params:
            intr_cfg = hw_config["dev_intr_cpu_configuration"] = {}
            intr_cfg["irq_devs"] = {}
            intr_cfg["irqbalance_hosts"] = []

            hosts = []
            for dev in self.dev_interrupt_hw_config_dev_list:
                if dev.host not in hosts:
                    hosts.append(dev.host)
            for host in hosts:
                host.run("service irqbalance stop")
                intr_cfg["irqbalance_hosts"].append(host)

            for dev in self.dev_interrupt_hw_config_dev_list:
                # TODO better service handling through HostAPI
                self._pin_dev_interrupts(dev, self.params.dev_intr_cpu)
                intr_cfg["irq_devs"][dev] = self.params.dev_intr_cpu

    def hw_deconfig(self, config):
        intr_config = config.hw_config.get("dev_intr_cpu_configuration", {})
        for host in intr_config.get("irqbalance_hosts", []):
            host.run("service irqbalance start")

        super().hw_deconfig(config)

    def describe_hw_config(self, config):
        desc = super().describe_hw_config(config)

        hw_config = config.hw_config

        intr_cfg = hw_config.get("dev_intr_cpu_configuration", None)
        if intr_cfg:
            desc += [
                "{} irqbalance stopped".format(host.hostid)
                for host in intr_cfg["irqbalance_hosts"]
            ]
            desc += [
                "{}.{} irqs bound to cpu {}".format(
                    dev.host.hostid, dev._id, cpu
                )
                for dev, cpu in intr_cfg["irq_devs"].items()
            ]
        else:
            desc.append("Device irq configuration skipped.")
        return desc

    def _pin_dev_interrupts(self, dev, cpus):
        netns = dev.netns
        self._check_cpu_validity(netns, cpus)

        intrs = self._get_dev_interrupts(dev)

        for i, intr in enumerate(intrs):
            try:
                cpu = cpus[i % len(cpus)]
                netns.run(
                    "echo -n {} > /proc/irq/{}/smp_affinity_list".format(
                        cpu, intr
                    )
                )
            except ValueError:
                pass

    def _check_cpu_validity(self, host, cpus):
        cpu_info = host.run("lscpu", job_level=ResultLevel.DEBUG).stdout
        regex = "CPU\(s\): *([0-9]*)"
        num_cpus = int(re.search(regex, cpu_info).groups()[0])
        for cpu in cpus:
            if cpu < 0 or cpu > num_cpus - 1:
                raise RecipeError(
                    "Invalid CPU value given: %d. Accepted value %s."
                    % (
                        cpu,
                        "is: 0" if num_cpus == 1 else "are: 0..%d" % (num_cpus - 1),
                    )
                )

    def _get_dev_interrupts(self, dev):
        if "up" not in dev.state:
            # device needs to be UP when grepping /proc/interrupts
            dev.up()
            set_down = True
        else:
            set_down = False

        dev_id_regex = r"({})|({})".format(dev.name, dev.bus_info)
        res = dev.netns.run(
            "grep -P \"{}\" /proc/interrupts | cut -f1 -d: | sed 's/ //'".format(
                dev_id_regex
            ),
            job_level=ResultLevel.DEBUG,
        )

        if set_down:
            # set device back down if we set it up
            dev.down()

        return [int(intr.strip()) for intr in res.stdout.strip().split('\n')]
