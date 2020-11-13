from lnst.Recipes.ENRT.PerfTestMixins import (
    SctpFirewallPerfTestMixin,
    UdpFragmentationPerfTestMixin,
    DropCachesPerfTestMixin,
)


class CommonPerfTestTweakMixin(
    SctpFirewallPerfTestMixin,
    UdpFragmentationPerfTestMixin,
    DropCachesPerfTestMixin,
):
    pass
