from lnst.Recipes.ENRT.ConfigMixins.BaseHWConfigMixin import BaseHWConfigMixin


class ParallelStreamQDiscHWConfigMixin(BaseHWConfigMixin):
    def hw_config(self, config):
        super().hw_config(config)

        hw_config = config.hw_config

        parallel_streams = getattr(self.params, "perf_parallel_streams", None)
        if parallel_streams is not None and parallel_streams > 1:
            hw_config["parallel_stream_devs"] = []
            for dev in self.hw_config_dev_list:
                dev.host.run("tc qdisc replace dev %s root mq" % dev.name)
                hw_config["parallel_stream_devs"].append(dev)

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
