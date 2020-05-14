class BaseHWConfigMixin(object):
    def hw_config(self, config):
        config.hw_config = {}

    def hw_deconfig(self, config):
        del config.hw_config

    def describe_hw_config(self, config):
        return []

    def _configure_dev_attribute(self, config, dev_list, attr_name, value):
        hw_config = config.hw_config
        attr_cfg = hw_config[attr_name + "_configuration"] = {}
        for dev in dev_list:
            attr_cfg[dev] = {}
            attr_cfg[dev]["original"] = getattr(dev, attr_name)
            setattr(dev, attr_name, value)
            attr_cfg[dev]["configured"] = getattr(dev, attr_name)

    def _describe_dev_attribute(self, config, attr_name):
        hw_config = config.hw_config
        res = []
        try:
            attr = hw_config[attr_name + "_configuration"]
        except:
            res.append("{} configuration skipped.".format(attr_name))
            return res

        for dev, info in attr.items():
            res.append(
                "{}.{}.{} configured to {}, original value {}".format(
                    dev.host.hostid,
                    dev.name,
                    attr_name,
                    info["configured"],
                    info["original"],
                )
            )

        return res
