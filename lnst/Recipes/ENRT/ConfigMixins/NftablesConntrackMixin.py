import time

from .FirewallMixin import NftablesMixin
from lnst.Recipes.ENRT.ConfigMixins.FirewallMixin import NftablesMixin


class NftablesConntrackMixin(NftablesMixin):
    @NftablesMixin.firewall_rulesets.getter
    def firewall_rulesets(self):
        nic = self.matched.host2.eth0.name
        ruleset = (
            f"""table inet NotrackUnrelatedTraffic {{
  chain controllerInfNoTrackIn {{
    type filter hook prerouting priority raw;

    iif != {nic} counter notrack
    policy accept
  }}
  chain controllerInfNoTrackOut {{
    type filter hook output priority raw;

    iif != {nic} counter notrack
    policy accept
  }}
  chain InterfaceUnderTest {{
    type filter hook input priority 0; policy accept;

    # Allow established connections to pass
    iif {nic} ct state {{ new, established, related }} accept
  }}
}}"""
        )
        return {self.matched.host2: ruleset}

    def apply_sub_configuration(self, config):
        super().apply_sub_configuration(config)
        host2 = self.matched.host2

        host2.run("sysctl -w net.netfilter.nf_conntrack_tcp_timeout_syn_sent=3600")
        # ^^ unloading the module in remove_sub_configuration() will reset it

    def remove_sub_configuration(self, config):
        # conntrack-related modules to be unloaded to not 
        # interfere with following tests. Also, it flushes
        # conntrack table.
        super().remove_sub_configuration(config)

        host2 = self.matched.host2

        # NOTE: sleeps are necessary to let kernel actually unload the modules
        host2.run("systemctl stop nftables")
        time.sleep(2)
        host2.run("modprobe -rv nft_ct")
        time.sleep(10)  # may take a while, it clears conntrack table
        host2.run("modprobe -rv nf_conntrack_netlink")
        time.sleep(10)
        host2.run("modprobe -rv nf_conntrack")
        time.sleep(2)
        host2.run("modprobe -rv nft_counter")

