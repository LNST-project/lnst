from abc import ABC, abstractmethod
from lnst.Recipes.ENRT.ConfigMixins import BaseSubConfigMixin
from lnst.RecipeCommon.FirewallControl import FirewallControl
import copy

class FirewallMixin(BaseSubConfigMixin, ABC):
    """
    A config mixin to apply custom firewall rulesets on hosts.
    Do not inherit directly, use one of the derived classes below instead.
    """

    _fwctl = {}

    def fwctl(self, host):
        try:
            return self._fwctl[host]
        except KeyError:
            self._fwctl[host] = host.init_class(FirewallControl)
            return self._fwctl[host]

    @property
    def firewall_rulesets(self):
        """
        This property holds a dictionary of firewall rulesets in textual
        representation, indexed by the host it should be applied to. A typical
        use is:

        { self.matched.host1: <host1 ruleset>,
          self.matched.host2: <host2 ruleset> }

        This property is used by the default `firewall_rules_generator()`
        method. Overwriting the latter from a recipe constitutes an alternative
        to implementing it.

        The rulesets will be applied by a derived class's _apply_ruleset()
        method, i.e. typically fed into 'nft -f' or 'iptables-restore'.
        """
        return {}

    @firewall_rulesets.setter
    def firewall_rulesets(self, rulesets):
        """
        This setter is called with all hosts' rulesets after each test run.
        Overwrite it to perform post processing or analysis on contained state.
        """
        pass

    @property
    def firewall_rulesets_generator(self):
        """
        A generator yielding { host: ruleset, ... } to apply for a test run.
        Each yield will turn into a new sub configuration and thus be tested
        separately.
        """
        return [self.firewall_rulesets]

    def generate_sub_configurations(self, config):
        for parent_config in super().generate_sub_configurations(config):
            for rulesets in self.firewall_rulesets_generator:
                new_config = copy.copy(parent_config)
                new_config.firewall_rulesets = rulesets
                yield new_config

    @abstractmethod
    def _apply_ruleset(self, host, ruleset):
        ...

    def apply_sub_configuration(self, config):
        super().apply_sub_configuration(config)

        stored = {}
        for host, ruleset in config.firewall_rulesets.items():
            stored[host] = self._apply_ruleset(host, ruleset)
        config.stored_firewall_rulesets = stored

    def generate_sub_configuration_description(self, config):
        desc = super().generate_sub_configuration_description(config)

        for host, ruleset in config.firewall_rulesets.items():
            nlines = len(ruleset.split("\n"))
            desc.append(f"Firewall: ruleset with {nlines} lines on host {host}")

        return desc

    def remove_sub_configuration(self, config):
        applied = {}
        for host, ruleset in config.stored_firewall_rulesets.items():
            applied[host] = self._apply_ruleset(host, ruleset)
        self.firewall_rulesets = applied

        del config.stored_firewall_rulesets
        del config.firewall_rulesets

        return super().remove_sub_configuration(config)

class NftablesMixin(FirewallMixin):
    """
    An nftables backend for FirewallMixin.
    """

    def _apply_ruleset(self, host, ruleset):
        old = self.fwctl(host).apply_nftables_ruleset(ruleset.encode('utf-8'))
        return old.decode('utf-8')

class IptablesBaseMixin(FirewallMixin):
    """
    A common base class for all the iptables-like FirewallMixin backends.
    Do not inherit directly, use one of the *tablesMixin classes instead.
    """

    @property
    @abstractmethod
    def iptables_command(self):
        ...

    def _apply_ruleset(self, host, ruleset):
        ruleset = ruleset.encode('utf-8')
        cmd = self.iptables_command.encode('utf-8')
        old = self.fwctl(host).apply_iptableslike_ruleset(cmd, ruleset)
        return old.decode('utf-8')

class IptablesMixin(IptablesBaseMixin):
    """
    An iptables backend for FirewallMixin.
    """

    @property
    def iptables_command(self):
        return "iptables"

class Ip6tablesMixin(IptablesBaseMixin):
    """
    An ip6tables backend for FirewallMixin.
    """

    @property
    def iptables_command(self):
        return "ip6tables"

class EbtablesMixin(IptablesBaseMixin):
    """
    An ebtables backend for FirewallMixin.
    """

    @property
    def iptables_command(self):
        return "ebtables"

class ArptablesMixin(IptablesBaseMixin):
    """
    An arptables backend for FirewallMixin.
    """

    @property
    def iptables_command(self):
        return "arptables"
