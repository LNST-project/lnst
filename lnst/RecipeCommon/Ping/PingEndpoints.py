class PingEndpoints():
    def __init__(self, endpoint1, endpoint2, reachable=True):
        self.endpoints = [endpoint1, endpoint2]
        self.reachable = reachable

    @property
    def endpoints(self):
        return self._endpoints

    @endpoints.setter
    def endpoints(self, endpoints):
        self._endpoints = endpoints

    @property
    def reachable(self):
        return self._reachable

    @reachable.setter
    def reachable(self, reachable):
        self._reachable = reachable
