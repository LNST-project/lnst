from lnst.Common.Parameters import ListParam
from lnst.Recipes.ENRT.ConfigMixins.BaseHWConfigMixin import BaseHWConfigMixin
from lnst.Recipes.ENRT.ConfigMixins.DevInterruptTools import pin_dev_interrupts


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
                pin_dev_interrupts(dev, self.params.dev_intr_cpu)
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
