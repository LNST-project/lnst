from lnst.Common.Parameters import IntParam, StrParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.RecipeCommon.Ping.Recipe import PingConf, PingTestAndEvaluate

class PingFloodRecipe(PingTestAndEvaluate):
    driver = StrParam(default='ixgbe')
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    src_addr = StrParam(default = "192.168.1.1/24")
    dst_addr = StrParam(default = "192.168.1.2/24")
    count = IntParam(default = 100)
    interval = StrParam(default = 0.2)
    size = IntParam(mandatory = False)
    mtu = IntParam(mandatory = False)

    def test(self):
        host1, host2 = self.matched.host1, self.matched.host2

        host1.eth0.ip_add(ipaddress(self.params.src_addr))
        host2.eth0.ip_add(ipaddress(self.params.dst_addr))

        if "mtu" in self.params:
            host1.eth0.mtu = self.params.mtu
            host2.eth0.mtu = self.params.mtu

        host1.eth0.up()
        host2.eth0.up()

        ip1 = host1.eth0.ips[0]
        ip2 = host2.eth0.ips[0]
        cn = self.params.count
        iv = self.params.interval
        if "size" in self.params:
            sz = self.params.size
        else:
            sz = None

        pcfg=PingConf(host1, ip1, host2, ip2, count = cn, interval = iv,
            size = sz)
        result = self.ping_test([pcfg])
        self.ping_report_and_evaluate(result)
