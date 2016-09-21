"""
Copyright 2016 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jiri@mellanox.com (Jiri Pirko)
idosch@mellanox.com (Ido Schimmel)
"""

from time import sleep
import logging
import re

class RunCmdException(Exception):
    pass

class TestLib:
    def __init__(self, ctl, aliases):
        self._ctl = ctl
        self._ipv = aliases["ipv"]
        self._mtu = int(aliases["mtu"])
        if "netperf_duration" in aliases:
            self._netperf_duration = int(aliases["netperf_duration"])
        if "netperf_num_parallel" in aliases:
            self._netperf_num_parallel = int(aliases["netperf_num_parallel"])
        if "mc_low_thershold" in aliases:
            self._mc_low_thershold = int(aliases["mc_low_thershold"])
        else:
            self._mc_low_thershold = 1000
        if "mc_high_thershold" in aliases:
            self._mc_high_thershold = int(aliases["mc_high_thershold"])
        else:
            self._mc_high_thershold = 10000000
        if "mc_speed" in aliases:
            self._mc_speed = int(aliases["mc_speed"])
        else:
            self._mc_speed = 1000

    def _generate_default_desc(self, if1, ifs):
        ret = "from %s->%s to " % (if1.get_host().get_id(), if1.get_id())
        for i in ifs:
            ret += "%s->%s" % (i.get_host().get_id(), i.get_id())
            if i != ifs[-1]:
                ret += ", "
        return ret

    def linkneg(self, if1, if2, state, speed=0, timeout=5, desc=None):
        if not desc:
            desc = self._generate_default_desc(if1, [if2])

        m2 = if2.get_host()
        m2.sync_resources(modules=["LinkNeg"])

        linkneg_mod = self._ctl.get_module("LinkNeg",
                                           options={
                                           "iface": if2.get_devname(),
                                           "state": state,
                                           "speed": speed,
                                           "timeout": timeout})

        if speed:
            # Make sure the link at the other end advertises all of
            # its supported speeds.
            if2.set_autoneg()
            sleep(3)

            # Setting the speed causes the link to first go down, so make
            # sure LinkNeg will only get the following up event by sleeping
            # for one second.
            if1.set_speed(speed)
            sleep(1)
        elif state:
            if1.set_link_up()
        else:
            if1.set_link_down()

        m2.run(linkneg_mod, desc=desc, netns=if2.get_netns())

    def ping_simple(self, if1, if2, fail_expected=False, desc=None,
                    limit_rate=90, count=100, interval=0.2):
        if not desc:
            desc = self._generate_default_desc(if1, [if2])

        if1.set_mtu(self._mtu)
        if2.set_mtu(self._mtu)

        m1 = if1.get_host()
        m1.sync_resources(modules=["Icmp6Ping", "IcmpPing"])

        ping_mod = self._ctl.get_module("IcmpPing",
                                        options={
                                        "addr": if2.get_ip(0),
                                        "count": count,
                                        "interval": interval,
                                        "iface" : if1.get_devname(),
                                        "limit_rate": limit_rate})

        ping_mod6 = self._ctl.get_module("Icmp6Ping",
                                         options={
                                         "addr": if2.get_ip(1),
                                         "count": count,
                                         "interval": interval,
                                         "iface" : if1.get_ip(1),
                                         "limit_rate": limit_rate})

        if self._ipv in [ 'ipv6', 'both' ]:
            m1.run(ping_mod6, fail_expected=fail_expected, desc=desc, netns=if1.get_netns())

        if self._ipv in [ 'ipv4', 'both' ]:
            m1.run(ping_mod, fail_expected=fail_expected, desc=desc, netns=if1.get_netns())

    def _get_netperf_srv_mod(self, if1, is_ipv6):
        if is_ipv6:
            addr_index = 1
        else:
            addr_index = 0
        modules_options = {
            "role" : "server",
            "bind" : if1.get_ip(addr_index)
        }
        if is_ipv6:
            modules_options["netperf_opts"] = "-6"
        return self._ctl.get_module("Netperf", options = modules_options)

    def _get_netperf_cli_mod(self, if1, if2, testname,
                             duration, num_parallel, is_ipv6):
        if is_ipv6:
            ipv6_str = " -6"
            addr_index = 1
        else:
            ipv6_str = ""
            addr_index = 0
        modules_options = {
            "role" : "client",
            "netperf_server" : if1.get_ip(addr_index),
            "duration" : duration,
            "num_parallel" : num_parallel,
            "testname" : testname,
            "netperf_opts" : "-L %s%s" % (if2.get_ip(addr_index), ipv6_str),
            "testoptions" : "-R 1",
        }
        return self._ctl.get_module("Netperf", options = modules_options)

    def _run_netperf(self, if1, if2, testname, is_ipv6, desc):
        if not desc:
            desc = self._generate_default_desc(if1, [if2])

        m1 = if1.get_host()
        m2 = if2.get_host()

        m1.sync_resources(modules=["Netperf"])
        m2.sync_resources(modules=["Netperf"])

        duration = self._netperf_duration
        num_parallel = self._netperf_num_parallel

        server_proc = m1.run(self._get_netperf_srv_mod(if1, is_ipv6), bg=True, netns=if1.get_netns())
        self._ctl.wait(2)
        netperf_cli_mod = self._get_netperf_cli_mod(if1, if2, testname,
                                                    duration, num_parallel,
                                                    is_ipv6)
        m2.run(netperf_cli_mod, timeout=duration + 10, desc=desc, netns=if2.get_netns())
        server_proc.intr()

    def _netperf(self, if1, if2, testname, desc):
        if1.set_mtu(self._mtu)
        if2.set_mtu(self._mtu)

        if self._ipv in [ 'ipv4', 'both' ]:
            self._run_netperf(if1, if2, testname, False, desc)

        if self._ipv in [ 'ipv6', 'both' ]:
            self._run_netperf(if1, if2, testname, True, desc)

    def netperf_tcp(self, if1, if2, desc=None):
        self._netperf(if1, if2, "TCP_STREAM", desc)

    def netperf_udp(self, if1, if2, desc=None):
        self._netperf(if1, if2, "UDP_STREAM", desc)

    def _get_iperf_srv_mod(self, mc_group):
        modules_options = {
            "role" : "server",
            "bind" : mc_group,
            "iperf_opts" : "-u"
        }
        return self._ctl.get_module("Iperf", options = modules_options)

    def _get_iperf_cli_mod(self, mc_group, duration, speed):
        modules_options = {
            "role" : "client",
            "iperf_server" : mc_group,
            "duration" : duration,
            "iperf_opts" : "-u -b " + str(speed) + "mb"
        }
        return self._ctl.get_module("Iperf", options = modules_options)

    def iperf_mc(self, sender, listeners, bridged, mc_group, desc=None):
        if not desc:
            desc = self._generate_default_desc(sender, listeners)

        sender.set_mtu(self._mtu)
        sender.enable_multicast()
        map(lambda i:i.enable_multicast(), listeners + bridged)
        map(lambda i:i.set_mtu(self._mtu), listeners + bridged)

        sender_host = sender.get_host()
        listeners_host = map(lambda i:i.get_host(), listeners)
        bridged_host = map(lambda i:i.get_host(), bridged)

        map(lambda i:i.sync_resources(modules=["Iperf"]),
            listeners_host + bridged_host)

        duration = self._netperf_duration
        speed = self._mc_speed

        # read link-stats
        sender_stats = sender.link_stats()
        listeners_stats = map(lambda i:i.link_stats(), listeners)
        bridged_stats = map(lambda i:i.link_stats(), bridged)

        # Run iperf server for all listeners
        srv_m = self._get_iperf_srv_mod(mc_group)
        s_procs = map(lambda i:i[0].run(srv_m, bg=True, netns=i[1].get_netns()),
                      zip(listeners_host, listeners))
        self._ctl.wait(2)

        # An send traffic to all listeners but bridged
        cli_m = self._get_iperf_cli_mod(mc_group, duration, speed)
        sender_host.run(cli_m, timeout=duration + 10, desc=desc,
                        netns=sender.get_netns())
        map(lambda i:i.intr(), s_procs)
        map(lambda i:i.disable_multicast(), listeners + bridged)
        sender.disable_multicast()

        # re-read link-stats
        sender_stats1 = sender.link_stats()
        listeners_stats1 = map(lambda i:i.link_stats(), listeners)
        bridged_stats1 = map(lambda i:i.link_stats(), bridged)

        # Check that listeners got multi cast traffic
        tx = sender_stats1["tx_bytes"] - sender_stats["tx_bytes"]
        rx = map(lambda i:i[1]["rx_bytes"] - i[0]["rx_bytes"],
                 zip(listeners_stats, listeners_stats1))
        err = filter(lambda i:i[0] < self._mc_high_thershold, zip(rx, listeners))
        err_str = map(lambda i:("Traffic isn't received for %s:%s count %d" %
                               (i[1].get_host().get_id(), i[1].get_id(), i[0]),
                               i[1]), err)
        for i in err_str:
            self.custom(i[1].get_host(), "iperf_mc", i[0])
        for i in zip(rx, listeners):
            logging.info("Measured traffic on %s:%s is %dMb, bytes lost %d (%d%%)" %
                         (i[1].get_host().get_id(), i[1].get_id(),
                          i[0] / 1000000,
                          max(tx - i[0], 0),
                          (max(tx - i[0], 0) * 100) / tx))

        # Check that only listeners got traffic
        rx = map(lambda i:i[1]["rx_bytes"] - i[0]["rx_bytes"],
                 zip(bridged_stats, bridged_stats1))
        err = filter(lambda i:i[0] > self._mc_low_thershold, zip(rx, bridged))
        err_str = map(lambda i:("Received unwanted traffic for %s:%s count %d" %
                               (i[1].get_host().get_id(), i[1].get_id(), i[0]),
                               i[1]), err)
        for i in err_str:
            self.custom(i[1].get_host(), "iperf_mc", i[0])

    def pktgen(self, if1, if2, pkt_size, desc=None, thread_option=[]):
        if1.set_mtu(self._mtu)
        m1 = if1.get_host()
        m1.sync_resources(modules=["PktgenTx"])

        pktgen_option = ["count 10000", "clone_skb 0", "delay 0"]
        pktgen_option.append("pkt_size %s" % pkt_size)
        pktgen_option.append("dst_mac %s" % if2.get_hwaddr())
        pktgen_option.append("dst %s" % if2.get_ip(0))
        if not thread_option:
            dev_names = if1.get_devname()
        else:
            dev_names = ["{}@{}".format(if1.get_devname(), idx) for idx in
                         range(len(thread_option))]
        pktgen_mod = self._ctl.get_module("PktgenTx",
                                          options={
                                          "netdev_name": dev_names,
                                          "pktgen_option": pktgen_option,
                                          "thread_option": thread_option})

        m1.run(pktgen_mod, desc=desc, netns=if1.get_netns())

    def custom(self, m1, desc, err_msg=None):
        m1.sync_resources(modules=["Custom"])
        options = {}
        if err_msg:
            options["fail"] = "yes"
            options["msg"] = err_msg
        custom_mod = self._ctl.get_module("Custom", options=options)
        m1.run(custom_mod, desc=desc)

    def check_fdb(self, iface, hwaddr, vlan_id, rec_type, find=True):
        fdb_table = iface.get_br_fdbs()

        rec = "offload" if rec_type == "software" else "self"
        found = False
        for fdb in fdb_table:
            if (fdb["hwaddr"] == str(hwaddr) and fdb["vlan_id"] == vlan_id and
                fdb[rec]):
                found = True

        if found and not find:
            err_msg = "found %s record when shouldn't" % rec_type
        elif find and not found:
            err_msg = "didn't find %s record when should've" % rec_type
        else:
            err_msg = ""

        self.custom(iface.get_host(), "fdb test", err_msg)

    def _lldp_set(self, iface, tlv_name, arg_name, arg):
        iface_name = iface.get_devname()
        m = iface.get_host()

        cmd = "lldptool -i {} -V {} -T {}={}".format(iface_name, tlv_name,
                                                     arg_name, arg)
        m.run(cmd)

    def lldp_ets_default_set(self, iface, willing=True):
        up2tc = ','.join(["{}:0".format(x) for x in range(8)])
        self._lldp_set(iface, "ETS-CFG", "up2tc", up2tc)

        tsa = ','.join(["{}:strict".format(x) for x in range(8)])
        self._lldp_set(iface, "ETS-CFG", "tsa", tsa)

        willing = "yes" if willing else "no"
        self._lldp_set(iface, "ETS-CFG", "willing", willing)

        self._lldp_set(iface, "ETS-CFG", "enableTx", "yes")

    def lldp_ets_up2tc_set(self, iface, up2tc):
        up2tc = ','.join(["{}:{}".format(x[0], x[1]) for x in up2tc])
        self._lldp_set(iface, "ETS-CFG", "up2tc", up2tc)

    def lldp_ets_tsa_set(self, iface, tsa, tcbw):
        tsa = ','.join(["{}:{}".format(prio, algo) for prio, algo in tsa])
        self._lldp_set(iface, "ETS-CFG", "tsa", tsa)

        tcbw_proper = [0] * 8
        for prio, bw in tcbw:
            tcbw_proper[prio] = bw
        tcbw = ','.join(map(str, tcbw_proper))
        self._lldp_set(iface, "ETS-CFG", "tcbw", tcbw)

    def lldp_pfc_set(self, iface, prio, willing=True, delay=0):
        prio = "none" if prio == [] else ','.join(map(str, prio))
        self._lldp_set(iface, "PFC", "enabled", prio)

        willing = "yes" if willing else "no"
        self._lldp_set(iface, "PFC", "willing", willing)

        self._lldp_set(iface, "PFC", "delay", delay)

    def run_json_cmd(self, host, cmd):
        cmd = host.run(cmd, json=True)
        if not cmd.passed():
            raise RunCmdException(cmd.get_result()["res_data"]["stderr"])
        return cmd.out()

    def devlink_clearmax(self, m, devlink_dev):
        m.run("devlink sb occupancy clearmax {}".format(devlink_dev))

    def _devlink_occ_snapshot(self, iface):
        iface_name = iface.get_devname()
        m = iface.get_host()
        devlink_dev = iface.get_devlink_name()

        m.run("devlink sb occupancy snapshot {}".format(devlink_dev))
        cmd = "devlink sb occupancy show {} -j".format(iface_name)
        return self.run_json_cmd(m, cmd)

    def devlink_tc_max_occ_get(self, iface, ingress, tc):
        d = self._devlink_occ_snapshot(iface)
        ie_tc = "itc" if ingress else "etc"
        iface_name = iface.get_devname()

        return d["occupancy"][unicode(iface_name)][ie_tc][str(tc)]["max"]

    def _devlink_port_tc_pool_get(self, iface, tc, ingress):
        iface_name = iface.get_devname()
        m = iface.get_host()
        devlink_dev = iface.get_devlink_name()

        ingress = "ingress" if ingress else "egress"
        cmd = "devlink sb tc bind show {} tc {} type {} -j"
        d = self.run_json_cmd(m, cmd.format(iface_name, tc, ingress))
        return d["tc_bind"][unicode(iface_name)][0]["pool"]

    def _devlink_pool_size_get(self, m, devlink_dev, pool):
        cmd = "devlink sb pool show {} pool {} -j"
        d = self.run_json_cmd(m, cmd.format(devlink_dev, pool))

        return d["pool"][devlink_dev][0]["size"]

    def devlink_pool_thtype_set(self, m, devlink_dev, pool, static):
        pool_size = self._devlink_pool_size_get(m, devlink_dev, pool)

        cmd = "devlink sb pool set {} pool {} size {} thtype {}"
        m.run(cmd.format(devlink_dev, pool, pool_size,
                         "static" if static else "dynamic"))

    def devlink_port_tc_quota_set(self, iface, tc, ingress, pool, th):
        ingress = "ingress" if ingress else "egress"
        iface_name = iface.get_devname()
        m = iface.get_host()

        cmd = "devlink sb tc bind set {} tc {} type {} pool {} th {}"
        m.run(cmd.format(iface_name, tc, ingress, pool, th))

    def devlink_port_quota_set(self, iface, pool, th):
        iface_name = iface.get_devname()
        m = iface.get_host()

        cmd = "devlink sb port pool set {} pool {} th {}"
        m.run(cmd.format(iface_name, pool, th))

    def devlink_port_etc_quota_max_set(self, iface, tc):
        devlink_dev = iface.get_devlink_name()
        m = iface.get_host()
        pool = self._devlink_port_tc_pool_get(iface, tc, False)
        pool_size = self._devlink_pool_size_get(m, devlink_dev, pool)

        self.devlink_pool_thtype_set(m, devlink_dev, pool, True)
        self.devlink_port_quota_set(iface, pool, pool_size)
        self.devlink_port_tc_quota_set(iface, tc, False, pool, pool_size)
