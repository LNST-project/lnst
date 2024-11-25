from lnst.Common.Parameters import ChoiceParam, ConstParam, StrParam
from lnst.RecipeCommon.Perf.Measurements import RDMABandwidthMeasurement
from lnst.Recipes.ENRT.SimpleNetworkRecipe import SimpleNetworkRecipe
from lnst.RecipeCommon.Perf.Recipe import RecipeConf


class SoftwareRDMARecipe(SimpleNetworkRecipe):
    """
    RDMA / InfiniBand bandwidth test recipe
    """

    # rxe driver / siw driver
    software_rdma_type = ChoiceParam(type=StrParam, choices={"rxe", "siw"}, mandatory=True)

    # override BaseFlowMeasurementGenerator's incompatible params
    perf_tests = ConstParam(value=["rdma_stream"])
    net_perf_tool = ConstParam(value="rdma-measurement")
    ip_versions = ConstParam(value=["ipv4"])

    @property
    def net_perf_tool_class(self) -> type[RDMABandwidthMeasurement]:
        return RDMABandwidthMeasurement

    @property
    def device_name(self) -> str:
        return f"{self.params.software_rdma_type}0"

    def test_wide_configuration(self, config) -> RecipeConf:
        config = super().test_wide_configuration(config)
        host1, host2 = self.matched.host1, self.matched.host2

        # setup RDMA link, emulating InfiniBand on Ethernet
        for host in [host1, host2]:
            host.run(
                f"rdma link add {self.device_name} type {self.params.software_rdma_type} netdev {host.eth0.name}"
            )

        config.rdma_device_name = self.device_name
        return config

    def test_wide_deconfiguration(self, config: RecipeConf) -> None:
        host1, host2 = self.matched.host1, self.matched.host2

        for host in [host1, host2]:
            host.run(f"rdma link delete {self.device_name}")

        super().test_wide_deconfiguration(config)
