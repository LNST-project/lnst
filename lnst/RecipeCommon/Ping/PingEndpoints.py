from dataclasses import dataclass

from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint


@dataclass
class PingEndpointPair(EndpointPair[IPEndpoint]):
    """
    On top of the basic EndpointPair functionality, we want to ensure that
    endpoints that shouldn't be reachable are not reachable.
    """
    should_be_reachable: bool = True
