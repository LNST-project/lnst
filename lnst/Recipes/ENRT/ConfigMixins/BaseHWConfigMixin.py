class BaseHWConfigMixin(object):
    @property
    def hw_config_dev_list(self):
        return []

    def hw_config(self, config):
        config.hw_config = {}

    def hw_deconfig(self, config):
        del config.hw_config

    def describe_hw_config(self, config):
        return []

    def _configure_dev_attribute(self, config, attr_name, value):
        hw_config = config.hw_config
        if value:
            attr_cfg = hw_config[attr_name + "_configuration"] = {}
            for dev in self.hw_config_dev_list:
                attr_cfg[dev] = {}
                attr_cfg[dev]["original"] = getattr(dev, attr_name)
                setattr(dev, attr_name, value)
                attr_cfg[dev]["configured"] = getattr(dev, attr_name)

    def _describe_dev_attribute(self, config, attr_name):
        hw_config = config.hw_config
        res = []
        attr = hw_config.get(attr_name + "_configuration", None)
        if attr:
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
        else:
            res.append("{} configuration skipped.".format(attr_name))
        return res
