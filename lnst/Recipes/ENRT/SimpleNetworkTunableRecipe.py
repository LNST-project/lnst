from lnst.Common.Parameters import Param
from lnst.Recipes.ENRT.SimpleNetworkRecipe import BaseSimpleNetworkRecipe
from lnst.Recipes.ENRT.BaremetalEnrtRecipe import BaremetalEnrtCommonMixins
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe

from lnst.Recipes.ENRT.MeasurementGenerators.FlowMeasurementMultiCpupinGenerator import (
    FlowMeasurementMultiCpupinGenerator,
)
from lnst.Recipes.ENRT.MeasurementGenerators.FlowEndpointsStatCPUMeasurementGenerator import (
    FlowEndpointsStatCPUMeasurementGenerator,
)
from lnst.Recipes.ENRT.MeasurementGenerators.LinuxPerfMeasurementGenerator import (
    LinuxPerfMeasurementGenerator,
)

from lnst.Recipes.ENRT.ConfigMixins.MultiCoalescingHWConfigMixin import (
    MultiCoalescingHWConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.MultiDevInterruptHWConfigMixin import (
    MultiDevInterruptHWConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.DevRxHashFunctionConfigMixin import (
    DevRxHashFunctionConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.DevNfcRxFlowHashConfigMixin import (
    DevNfcRxFlowHashConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.DevQueuesConfigMixin import (
    DevQueuesConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.MTUHWConfigMixin import MTUHWConfigMixin
from lnst.Recipes.ENRT.ConfigMixins.PauseFramesHWConfigMixin import (
    PauseFramesHWConfigMixin,
)


class SimpleNetworkTunableRecipe(
    DevRxHashFunctionConfigMixin,
    DevNfcRxFlowHashConfigMixin,
    DevQueuesConfigMixin,
    PauseFramesHWConfigMixin,
    MultiCoalescingHWConfigMixin,
    MultiDevInterruptHWConfigMixin,
    MTUHWConfigMixin,
    OffloadSubConfigMixin,
    BaseSimpleNetworkRecipe,
    BaremetalEnrtCommonMixins,
    FlowEndpointsStatCPUMeasurementGenerator,
    LinuxPerfMeasurementGenerator,
    FlowMeasurementMultiCpupinGenerator,
    BaseEnrtRecipe,
):
    """
    This recipe implements Enrt testing for a simple network scenario that looks
    as follows

    .. code-block:: none

                    +--------+
             +------+ switch +-----+
             |      +--------+     |
          +--+-+                 +-+--+
        +-|eth0|-+             +-|eth0|-+
        | +----+ |             | +----+ |
        | host1  |             | host2  |
        +--------+             +--------+

    The recipe is similar to :any:`SimpleNetworkRecipe` with better control over
    the tuning of device settings such as:
    * device queues - :any:`DevQueuesConfigMixin`
    * nfc rx flow hash - :any:`DevNfcRxFlowHashConfigMixin`
    * rx hash function - :any:`DevRxHashFunctionConfigMixin`
    * per-device IRQ pinning - :any:`MultiDevInterruptHWConfigMixin`
    * per-device coalescing setting through :any:`MultiCoalescingHWConfigMixin`

    Also the recipe uses :any:`FlowMeasurementMultiCpupinGenerator`, that allows
    per-host CPU pinning strategies.
    """

    offload_combinations = Param(
        default=(
            dict(gro="on", gso="on", tso="on", tx="on", rx="on"),
            dict(gro="off", gso="on", tso="on", tx="on", rx="on"),
            dict(gro="on", gso="off", tso="off", tx="on", rx="on"),
            dict(gro="on", gso="on", tso="off", tx="off", rx="on"),
            dict(gro="on", gso="on", tso="on", tx="on", rx="off"),
        )
    )

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def pause_frames_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def offload_nics(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def coalescing_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
