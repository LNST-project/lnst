from trex_stl_lib.api import *
from trex.stl.trex_stl_hltapi import *

class UDPMultiflow(object):
    """
    Generate a many different UDP flows
    Port MAC and IP addresses are used
    Extra arguments in kwargs:
    msg_size: the size of the packet to use (default 64)
    port_id:  The port the stream will be added to
    """

    def create_stream (self, **kwargs):
        size = kwargs.get("msg_size", 64)
        L2 = Ether(src=kwargs["src_mac"], dst=kwargs["dst_mac"])
        L3 = IP(src=kwargs["src_ip"], dst=kwargs["dst_ip"])
        L4 = UDP()

        base_pkt = L2/L3/L4
        pad = max(0, size - len(base_pkt)) * 'x'
        base_pkt = base_pkt/pad

        vm = STLVM()
        vm.var(name = "src_port", min_value=1025, max_value=65000, size=2, op="inc")
        vm.var(name = "dst_port", min_value=1025, max_value=65000, size=2, op="dec")
        vm.write(fv_name = "src_port", pkt_offset = "UDP.sport")
        vm.write(fv_name = "dst_port", pkt_offset = "UDP.dport")

        pkt = STLPktBuilder(pkt = base_pkt, vm = vm)

        return STLStream(packet = pkt, mode = STLTXCont(percentage=100))

    def get_streams (self, direction = 0, **kwargs):
        # create 1 stream
        return [self.create_stream(**kwargs)]

# dynamic load - used for trex console or simulator
def register():
    return UDPMultiflow()
