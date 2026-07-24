from lnst.Recipes.ENRT.SimpleNetnsRouterRecipe import SimpleNetnsRouterRecipe
from lnst.Recipes.ENRT.ConfigMixins.FirewallMixin import NftablesMixin
from lnst.Common.Parameters import StrParam, IntParam, BoolParam

class NftablesRuleScaleRecipe(SimpleNetnsRouterRecipe, NftablesMixin):
    """
    This recipe combines SimpleNetnsRouterRecipe and NftablesMixin for testing
    routing throughput impact of specific nftables rules. To generate
    meaningful results, the rule is simply repeated multiple times, thereby
    amplifying the impact.
    Rules are added to host2's forwarding hook by default (defined by
    :any:`chainspec` parameter) which routes test traffic between host1 and a
    local netns.

    :param family:
        The family to use for the tested ruleset.
    :type family: :any:`StrParam` (default "inet")

    :param tablename:
        The name to use for the tested ruleset's table.
    :type tablename: :any:`StrParam` (default "t")

    :param chainname:
        The name to use for the tested ruleset's chain.
    :type chainname: :any:`StrParam` (default "c")

    :param chainspec:
        The hook spec of the chain to add rules to.
    :type chainspec: :any:`StrParam` (default "type filter hook forward priority filter")

    :param rule:
        The actual rule to insert repeatedly into the router's chain.
    :type rule: :any:`StrParam` representing the nftables rule.

    :param scale:
        The number of times to insert :any:`rule` into the ruleset.
    :type scale: :any:`IntParam` > 0

    :param flowtable:
        Whether to offload established connections to a flowtable or not.
        Besides creating a flowtable hooking into router's input and output
        interfaces, this will append a final rule matching on conntrack state
        'established' and adding the flow.
    :type flowtable: :any:`BoolParam` (default False)
    """
    family = StrParam(mandatory=False, default="inet")
    tablename = StrParam(mandatory=False, default="t")
    chainname = StrParam(mandatory=False, default="c")
    chainspec = StrParam(mandatory=False,
                         default="type filter hook forward priority filter")
    rule = StrParam(mandatory=True)
    scale = IntParam(mandatory=True)
    flowtable = BoolParam(mandatory=False, default=False)

    @property
    def firewall_rulesets_generator(self):
        family = self.params.get('family')
        tablename = self.params.get('tablename')
        chainname = self.params.get('chainname')
        chainspec = self.params.get('chainspec')
        rule = self.params.get('rule')
        scale = self.params.get('scale')
        f_t_c = f"{family} {tablename} {chainname}"
        ruleset = [
            "flush ruleset",
            f"add table {family} {tablename}",
            f"add chain {f_t_c} {{ {chainspec}; }}"
        ] + [f"add rule {f_t_c} {rule}"] * scale
        if self.params.get('flowtable'):
            devs = f"{self.matched.host2.eth0.name}, {self.matched.host2.pn0.name}"
            ftspec = f"hook ingress priority filter; devices = {{ {devs} }};"
            ruleset.append(f"add flowtable {family} {tablename} ft {{ {ftspec} }}")
            ruleset.append(f"add rule {f_t_c} ct state established flow add @ft")
        yield { self.matched.host2: "\n".join(ruleset) }

    def generate_sub_configuration_description(self, config):
        family = self.params.get('family')
        tablename = self.params.get('tablename')
        chainname = self.params.get('chainname')
        chainspec = self.params.get('chainspec')
        rule = self.params.get('rule')
        scale = self.params.get('scale')
        desc = super().generate_sub_configuration_description(config)
        msg = f"NftablesScale: Ruleset with {scale} times '{rule}'"
        msg += f" in a table named '{tablename}' and chain named '{chainname}'"
        msg += f" with '{chainspec}' in family '{family}'"
        if self.params.get('flowtable'):
            msg += " and a flowtable"
        desc.append(msg)
        return desc
