class BaseSubConfigMixin(object):
    """
    This is a base class that defines common API for specific *sub*
    configuration mixin classes.
    """

    def generate_sub_configurations(self, config):
        """
        A child class should override this method to extend the *test_wide*
        config with any data specific to the sub configuration, for example NIC
        offload settings. The child class must use a copy of the *config*.

        The data in the config is later used in :meth:`apply_sub_configuration`.

        The child class must include a :py:func:`super` call of this method so
        that all other mixin classes do their part of cooperative inheritance.
        """
        yield config

    def apply_sub_configuration(self, config):
        """
        A child class should override this method to perform the *sub*
        configuration, for example configure NIC offloads. Any data required to
        do the configuration should be added to *config* through the
        :meth:`generate_sub_configurations`.

        The child class must include a :py:func:`super` call of this method so
        that all other mixin classes do their part of cooperative inheritance.
        """
        pass

    def generate_sub_configuration_description(self, config):
        """
        A child class should override this method to append a mixin specific
        *sub* configuration description that would show up in the recipe log.

        The child class must include a :py:func:`super` call of this method so
        that all other mixin classes do their part of cooperative inheritance.
        """
        return ["Sub configuration description:"]

    def remove_sub_configuration(self, config):
        """
        A child class should override this method to perform a cleanup of the
        specific sub configuration, for example restore NIC offloads.

        Any data required to cleanup the configuration should be added to *config*
        through the :meth:`generate_sub_configurations`.

        The child class must include a :py:func:`super` call of this
        method so that all other mixin classes do their part of cooperative
        inheritance.
        """
        return
