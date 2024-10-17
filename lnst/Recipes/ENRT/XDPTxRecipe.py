from lnst.Common.Parameters import ConstParam
from lnst.Recipes.ENRT.ConfigMixins.MultiDevInterruptHWConfigMixin import (
    MultiDevInterruptHWConfigMixin,
)
from lnst.Recipes.ENRT.SimpleNetworkRecipe import SimpleNetworkRecipe
from lnst.Recipes.ENRT.MeasurementGenerators.XDPFlowMeasurementGenerator import (
    XDPFlowMeasurementGenerator,
)


class XDPTxRecipe(
    XDPFlowMeasurementGenerator, MultiDevInterruptHWConfigMixin, SimpleNetworkRecipe
):
    xdp_command = ConstParam(value="tx")
    # NOTE: Receiver's IRQs needs to be pinned to single CPU (due to test stability)
    # Generator needs to reach line rate, therefore its' IRQ CPUs should not be limited.
    # Simply use `multi_dev_interrupt_config` with single host.
