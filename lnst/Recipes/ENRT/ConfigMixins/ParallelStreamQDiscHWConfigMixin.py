from lnst.Recipes.ENRT.ConfigMixins.BaseHWConfigMixin import BaseHWConfigMixin


class ParallelStreamQDiscHWConfigMixin(BaseHWConfigMixin):
    """
    This class is an extension to the :any:`BaseEnrtRecipe` class that enables
    the mq (multiqueing) qdisc configuration on the devices defined by
    :attr:`parallel_stream_qdisc_hw_config_dev_list` property.

    The qdisc is configured when the :any:`BaseEnrtRecipe`'s *perf_parallel_streams*
    test parameter is set.

    """

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        """
        The value of this property is a list of devices for which the
        mq qdisc should be configured. It has to be defined by a derived class.
        """
        return []

    def hw_config(self, config):
        super().hw_config(config)

        hw_config = config.hw_config

        parallel_streams = getattr(self.params, "perf_parallel_streams", None)
        if parallel_streams is not None and parallel_streams > 1:
            hw_config["parallel_stream_devs"] = []
            for dev in self.parallel_stream_qdisc_hw_config_dev_list:
                dev.host.run("tc qdisc replace dev %s root mq" % dev.name)
                hw_config["parallel_stream_devs"].append(dev)

    def hw_deconfig(self, config):
        hw_config = config.hw_config
        parallel_devs = hw_config.get("parallel_stream_devs", None)
        if parallel_devs is not None:
            for dev in parallel_devs:
                dev.host.run("tc qdisc del dev %s root" % dev.name)
            del hw_config["parallel_stream_devs"]

        super().hw_deconfig(config)

    def describe_hw_config(self, config):
        desc = super().describe_hw_config(config)

        hw_config = config.hw_config

        parallel_devs = hw_config.get("parallel_stream_devs", None)
        if parallel_devs:
            for dev in parallel_devs:
                desc.append(
                    "{}.{} configured to use mq qdisc".format(
                        dev.host.hostid, dev.name
                    )
                )
        else:
            desc.append("Parallel streams qdisc configuration skipped.")
        return desc
