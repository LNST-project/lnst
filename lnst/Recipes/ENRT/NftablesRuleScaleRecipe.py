from lnst.Recipes.ENRT.SimpleNetnsRouterRecipe import SimpleNetnsRouterRecipe
from lnst.Recipes.ENRT.ConfigMixins.FirewallMixin import NftablesMixin
from lnst.Common.Parameters import StrParam, IntParam, BoolParam

class NftablesRuleScaleRecipe(SimpleNetnsRouterRecipe, NftablesMixin):
    """
    This recipe combines SimpleNetnsRouterRecipe and NftablesMixin for testing
    routing throughput impact of specific nftables rules. To generate
    meaningful results, the rule is simply repeated multiple times, thereby
    amplifying the impact.
    Rules are added to host2's forwarding hook which routes test traffic
    between host1 and a local netns.

    :param rule:
        The actual rule to insert repeatedly into the router's forwarding
        chain.
    :type rule: :any:`StrParam` representing the nftables rule.

    :param scale:
        The number of times to insert :any:`rule` into the ruleset.
    :type scale: :any:`IntParam` > 0

    :param flowtable:
        Whether to offload established connections to a flowtable or not.
    :type flowtable: :any:`BoolParam`
    """
    rule = StrParam(mandatory=True)
    scale = IntParam(mandatory=True)
    flowtable = BoolParam(mandatory=False, default=False)

    @property
    def firewall_rulesets_generator(self):
        rule = self.params.get('rule')
        scale = self.params.get('scale')
        ruleset = [
            "flush ruleset",
            "add table inet t",
            "add chain inet t forward { type filter hook forward priority filter; }",
        ] + [f"add rule inet t forward {rule}"] * scale
        if self.params.get('flowtable'):
            devs = f"{self.matched.host2.eth0.name}, {self.matched.host2.pn0.name}"
            ftspec = f"hook ingress priority filter; devices = {{ {devs} }};"
            ruleset.append(f"add flowtable inet t ft {{ {ftspec} }}")
            ruleset.append("add rule inet t forward ct state established flow add @ft")
        yield { self.matched.host2: "\n".join(ruleset) }

    def generate_sub_configuration_description(self, config):
        rule = self.params.get('rule')
        scale = self.params.get('scale')
        desc = super().generate_sub_configuration_description(config)
        msg = f"NftablesScale: Ruleset with {scale} times '{rule}'"
        if self.params.get('flowtable'):
            msg += " and a flowtable"
        desc.append(msg)
        return desc
