from time import sleep
from lnst.Controller.Task import ctl
from lnst.Common.Consts import MROUTE
import copy
import random

# The topology used is:
#
# +----------------------------------------------------+
# | switch                                             |
# |                                                    |
# |addr: 1.10        2.10        3.10  4.10  5.10      |
# |port:  if1         if2         if3   if4   if5      |
# |        +           +           +     +     +       |
# |        |           | br0       |     |     |       |
# |        |    +------+------+    |     |     |       |
# |        |    |             |    |     |     |       |
# +----------------------------------------------------+
#          |    |             |    |     |     |
#          |    |             |    |     |     |
# +------------------+   +-----------------------------+
# |        |    |    |   |    |    |     |     |       |
# |        +    +    |   |    +    +     +     +       |
# |port   if1  if2   |   |   if1  if2   if3   if4      |
# |addr:  1.1  2.1   |   |   2.2  3.2   4.2   5.2      |
# |                  |   |                             |
# | machine1         |   |  machine2                   |
# +------------------+   +-----------------------------+
#

def check_results(sw, tl, ifaces, ratios, expected):
    results = [r > 0.9 and r < 1.1 for r in ratios]
    err_indices = [i for i in range(len(results)) if results[i] != expected[i]]
    if err_indices != []:
        err_str = "Interfaces that got traffic are %s, while expected are %s" % \
                  (str(ratios), str(expected))
        tl.custom(sw, "iperf_mc", err_str)

class MrouteTest:
    def __init__(self, tl, hosts, ifaces):
        self.tl = tl
        self.m1, self.m2, self.sw = hosts
        m1_if1, m1_if2, m2_if1, m2_if2, m2_if3, m2_if4, sw_if1, \
        sw_br_m1, sw_br_m2, sw_if3, sw_if4, sw_if5, sw_if2 = ifaces

        self.sw_ports = [sw_if1, sw_if2, sw_if3, sw_if4, sw_if5]
        self.mach_ports = [m1_if1, m1_if2, m2_if1, m2_if2, m2_if3, m2_if4]
        self.port2vif = {}
        self.vif2port = {}

        team_config = '{"runner" : {"name" : "lacp"}}'
        self.unrif_lag = self.sw.create_team(slaves = [],
                                             config=team_config)

        self.sw_mach_conn = { sw_if1: [m1_if1], sw_if2: [m1_if2, m2_if1],
                              sw_if3: [m2_if2], sw_if4: [m2_if3], sw_if5: [m2_if4]
        }
        self.mach_sw_conn = { m1_if1: sw_if1, m1_if2: sw_if2, m2_if1: sw_if2,
                              m2_if2: sw_if3, m2_if3: sw_if4, m2_if4: sw_if5
        }

        sw_if2.set_br_mcast_snooping(False)

    def init(self):
        self.sw.mroute_init()
        self.sw.mroute_pim_init()

    def add_vif(self, port, vif_index):
        self.port2vif[port] = vif_index
        self.vif2port[vif_index] = port
        port.mroute_add_vif(vif_index)

    def del_vif_port(self, port):
        vif_index = self.port2vif[port]
        port.mroute_del_vif(vif_index)
        del self.port2vif[port]
        del self.vif2port[vif_index]

    def del_vif(self, vif_index):
        port = self.vif2port[vif_index]
        port.mroute_del_vif(vif_index)
        del self.port2vif[port]
        del self.vif2port[vif_index]

    def fini(self):
        self.sw.mroute_finish()

    def del_rif(self, port):
        self.unrif_lag.slave_add(port.get_id())

    def add_rif(self, port):
        self.unrif_lag.slave_del(port.get_id())
        port.set_link_up()

    def pimreg_add(self, vif_index):
        self.sw.mroute_add_vif_reg(vif_index)
        self.port2vif["pimreg"] = vif_index
        self.vif2port[vif_index] = "pimreg"

    def expect_mr_notifs(self, notif_type, num_min=1, num_max=1,
                         source_ip = None, source_vif = None, group_ip = None):
        num_notifs = 0
        for i in range(num_max):
            notif = self.tl.expect_mr_notif(self.sw, notif_type,
                                            none_ok = True)
            if notif == None:
                break
            num_notifs += 1

        if num_notifs < num_min:
            self.tl.custom(self.sw, "mroute notif", "did not get notification")

    def send_mc_traffic(self, group, source_port, num_packets):
        speed = 1000
        source_host = source_port.get_host()
        source_host.sync_resources(modules=["Iperf"])
        iperf = self.tl._get_iperf_cli_mod_packets(group, num_packets, speed)

        sleep(1)
        source_port.enable_multicast()
        tx_stats_before = source_port.link_stats()["tx_packets"]
        rx_stats_before = [port.link_stats()["rx_mcast"]
                           for port in self.mach_ports]
        source_host.run(iperf)
        sleep(1)
        tx_stats_after = source_port.link_stats()["tx_packets"]
        rx_stats_after = [port.link_stats()["rx_mcast"]
                          for port in self.mach_ports]
        source_port.disable_multicast()

        tx_stats = tx_stats_after - tx_stats_before
        rx_stats = [before - after
                    for before, after in zip(rx_stats_after, rx_stats_before)]
        return [float(stats)/tx_stats for stats in rx_stats]

    def test_fwd(self, group, source_port, dest_ports, pimreg = False):

        if source_port == "pimreg":
            return
        if source_port in dest_ports:
            dest_ports.remove(source_port)

        # other_ports are all ports but the source
        source_mach_port = self.sw_mach_conn[source_port][0]
        dest_mach_ports = [port for port in self.mach_ports \
                           if self.mach_sw_conn[port] in dest_ports]
        bridged_mach_ports = self.sw_mach_conn[source_port]

        # Ports that are expected to get traffic are:
        #  - Ports that are destination of the route
        #  - Ports that are bridged to the source port
        # Traffic should never get to the source port, not even if the route
        # points to it.
        expected_res = [(port in dest_mach_ports or port in bridged_mach_ports)
                        and port != source_mach_port for port in self.mach_ports]
        ratio = self.send_mc_traffic(group, source_mach_port, 100)
        check_results(self.sw, self.tl, self.mach_ports, ratio, expected_res)

        if pimreg:
            self.expect_mr_notifs(MROUTE.NOTIF_WHOLEPKT, 3, 200)

    def mroute_test(self, mroute):
        ivif = mroute["ivif"]
        evifs = mroute["evifs"]

        # if ivif unresolved or pimreg, don't test
        if ivif not in self.vif2port.keys() or self.vif2port[ivif] == "pimreg":
            return

        source_port = self.vif2port[ivif]
        dest_ports = [self.vif2port[evif] for evif in evifs
                      if evif in self.vif2port.keys()]

        pimreg = False
        if "pimreg" in dest_ports:
            pimreg = True
            dest_ports.remove("pimreg")

        # run legitimate traffic and check that it is forwarded
        self.test_fwd(mroute["group"], source_port, dest_ports, pimreg)

        # If the route is (*,G), check RPF failures, as (S,G) route RPF
        # failures are much more difficult to check
        if mroute["source"] == "0.0.0.0" and len(dest_ports) != 0:
            new_source_port = dest_ports[0]
            new_source_mach_port = self.sw_mach_conn[new_source_port][0]
            self.send_mc_traffic(mroute["group"], new_source_mach_port, 1)
            self.tl.expect_mr_notif(self.sw, MROUTE.NOTIF_WRONGVIF)

    def mroute_create(self, source, group, ivif, evifs, test = True):
        dest_ports = [self.vif2port[evif] for evif in evifs]
        source_port = self.vif2port[ivif]

        evif_ttls = {evif: 1 for evif in evifs}
        self.sw.mroute_add_mfc(source, group, ivif, evif_ttls)
        mroute = {"ivif": ivif, "evifs": copy.deepcopy(evifs),
                  "source": source, "group": group}
        if test:
            self.mroute_test(mroute)
        return mroute

    def mroute_remove(self, mroute, test = True):
        self.sw.mroute_del_mfc(mroute["source"], mroute["group"], mroute["ivif"])

        if test:
            self.test_fwd(mroute["group"], self.vif2port[mroute["ivif"]], [])

    def _random_evifs(self, ivif, starg):
        vifs = self.vif2port.keys()
        evifs = [evif for evif in vifs
                 if random.choice([True, False]) and evif != ivif]
        if starg:
            evifs += [ivif]
        return evifs

    def random_mroute_add(self, group, starg, ivif = None, test = True):
        vifs = self.vif2port.keys()

        if not ivif:
            ivif = random.choice(vifs)
        evifs = self._random_evifs(ivif, starg)
        if starg:
            source = "0.0.0.0"
        else:
            if self.vif2port[ivif] != "pimreg":
                source_port = self.sw_mach_conn[self.vif2port[ivif]][0]
                source = str(source_port.get_ip(0))
            else:
                source = "1.2.3.4"

        return self.mroute_create(source, group, ivif, evifs, test)
