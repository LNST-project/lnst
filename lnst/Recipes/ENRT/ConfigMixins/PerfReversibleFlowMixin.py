from lnst.Common.Parameters import BoolParam
from lnst.RecipeCommon.Perf.Measurements import Flow as PerfFlow


class PerfReversibleFlowMixin(object):
    """ Mixin class for reversing the performance test flows

    This only really makes sense for recipes that have asymmetric endpoints.

    For example:

        SimpleNetworkRecipe is symmetrical since both endpoints are of the same type (both plain interfaces).

        TeamRecipe is asymmetrical because one endpoint is a team device and the other is a plain interface.

    So TeamRecipe could use this mixin to indicate that the flow of traffic can be reversed.

    This can be controlled by the `perf_reverse` parameter:

    :param perf_reverse:
        Parameter used by the :any:`generate_flow_combinations` generator.
        To specify that the flow of traffic between the endpoints should be reversed.
    :type perf_reverse: :any:`BoolParam` (default False)
    """
    perf_reverse = BoolParam(default=False)

    def _create_perf_flow(self, perf_test, client_nic, client_bind, server_nic,
                          server_bind, msg_size) -> PerfFlow:
        if self.params.perf_reverse:
            return super()._create_perf_flow(perf_test, server_nic, server_bind,
                                             client_nic, client_bind, msg_size)
        else:
            return super()._create_perf_flow(perf_test, client_nic, client_bind,
                                             server_nic, server_bind, msg_size)
