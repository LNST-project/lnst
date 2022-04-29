from lnst.Common.Parameters import IntParam, Param, StrParam
from lnst.Tests.BaseTestModule import BaseTestModule, TestModuleError
from lnst.External.TRex.TRexLib  import TRexCli, TRexSrv, TRexError
from pprint import pformat


class TRexCommon(BaseTestModule):
    trex_dir = StrParam(mandatory=True)

class TRexClient(TRexCommon):
    ports = Param(mandatory=True)

    flows = Param(mandatory=True)

    module = StrParam(default="UDPSimple")

    duration = IntParam(mandatory=True)
    warmup_time = IntParam(default=5)

    msg_size = IntParam(default=64)

    server_hostname = StrParam(default="localhost")
    trex_stl_path = 'trex_client/interactive'

    def __init__(self, **kwargs):
        super(TRexClient, self).__init__(**kwargs)
        self.impl = TRexCli(self.params)

    def __repr__(self):
        string = f"""
            TrexClient(
                trex_dir={self.impl.params.trex_dir},
                module={self.impl.params.module},
                msg_size={self.impl.params.msg_size},
                ports={self.impl.params.ports},
                server_hostname={self.impl.params.server_hostname},
                flows={pformat(self.impl.params.flows)}
            )
        """

        return string

    def runtime_estimate(self):
        _duration_overhead = 5
        return (self.params.duration +
                self.params.warmup_time +
                _duration_overhead)

    def run(self):
        self._res_data={}
        try:
            rc = self.impl.run()
        except TRexError as e:
            #TRex errors aren't picklable so we wrap them like this
            raise TestModuleError(str(e))

        self._res_data = self.impl.get_results()
        return rc

class TRexServer(TRexCommon):
    #TODO make ListParam
    flows = Param(mandatory=True)

    cores = Param(mandatory=True)

    def __init__(self, **kwargs):
        super(TRexServer, self).__init__(**kwargs)
        self.impl = TRexSrv(self.params)

    def __repr__(self):
        string = f"""
            TrexServer(
                trex_dir={self.impl.params.trex_dir},
                cores={self.impl.params.cores},
                flows={pformat(self.impl.params.flows)}
            )
        """
        return string

    def run(self):
        self._res_data={}
        try:
            rc = self.impl.run()
        except TRexError as e:
            #TRex errors aren't picklable so we wrap them like this
            raise TestModuleError(str(e))

        self._res_data = self.impl.get_results()
        return rc
