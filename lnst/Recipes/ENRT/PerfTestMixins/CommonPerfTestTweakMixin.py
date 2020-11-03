from lnst.Recipes.ENRT.PerfTestMixins import (
        SctpFirewallPerfTestMixin,
        DropCachesPerfTestMixin,
        )

class CommonPerfTestTweakMixin(SctpFirewallPerfTestMixin, DropCachesPerfTestMixin):
    pass
