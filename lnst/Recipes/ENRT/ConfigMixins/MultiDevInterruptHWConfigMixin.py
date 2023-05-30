from lnst.Common.Parameters import DictParam
from lnst.Recipes.ENRT.ConfigMixins.BaseHWConfigMixin import BaseHWConfigMixin
from lnst.Recipes.ENRT.ConfigMixins.DevInterruptTools import pin_dev_interrupts


class MultiDevInterruptHWConfigMixin(BaseHWConfigMixin):
    """
    This class is an extension to the :any:`BaseEnrtRecipe` class that enables
    the CPU affinity (CPU pinning) of the test device IRQs. The test devices
    are defined by :attr:`dev_interrupt_hw_config_dev_list` property.

    This mixin is a "multi device" variant of the :any:`DevInterruptHWConfigMixin`
    and allows configuration of individual devices instead of sharing the same
    configuration. This may be required when different device IRQ pinning is
    required by a flow generator and receiver host.

     .. note::
        Note that this Mixin also stops the irqbalance service.

    :param multi_dev_interrupt_config:
        (optional test parameter) this is a dictionary of per device IRQ binding
        settings. The configuration is done per host per device, where each
        device has a list of CPU ids and a policy specified.
        The policy can be defined in following ways:
            * "all" - pin each device IRQ to all CPUs in the cpus list
            * "round-robin" - use one CPU from the cpus list for each
            test device IRQ, start from beginning if the number of IRQs
            is bigger than the number of CPUs

        Example:
        {
            "host1": {
                "eth1": {
                    "cpus": [0,1],
                    "cpu_policy": "all"
                },
            },
            "host2": {
                "eth1": {
                    "cpus": [2,3],
                    "cpu_policy": "round-robin"
                },
            }
        }
    """
    multi_dev_interrupt_config = DictParam(mandatory=False)

    def hw_config(self, config):
        super().hw_config(config)

        hw_config = config.hw_config

        device_settings = self._parse_device_settings(self.params.multi_dev_interrupt_config)
        if device_settings:
            intr_cfg = hw_config["dev_intr_cpu_configuration"] = {}
            intr_cfg["irq_devs"] = {}
            intr_cfg["irqbalance_hosts"] = []

        for dev, dev_config in device_settings.items():
            cpus = dev_config["cpus"]
            policy = dev_config["cpu_policy"]

            if not cpus:
                continue

            if dev.host not in intr_cfg["irqbalance_hosts"]:
                dev.host.run("service irqbalance stop")
                intr_cfg["irqbalance_hosts"].append(dev.host)

            # TODO better service handling through HostAPI
            pin_dev_interrupts(dev, cpus, policy)
            intr_cfg["irq_devs"][dev] = (cpus, policy)

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
                "{}.{} irqs bound to cpu {} with policy:{}".format(
                    dev.host.hostid, dev._id, cpu, policy
                )
                for dev, (cpu, policy) in intr_cfg["irq_devs"].items()
            ]
        else:
            desc.append("Device irq configuration skipped.")
        return desc
