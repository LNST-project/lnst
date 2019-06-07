class BaseSubConfigMixin(object):
    def generate_sub_configurations(self, config):
        yield config

    def apply_sub_configuration(self, config):
        pass

    def generate_sub_configuration_description(self, config):
        return []

    def remove_sub_configuration(self, config):
        return
