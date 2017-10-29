"""
Copyright 2016-2017 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jiri@mellanox.com (Jiri Pirko)
idosch@mellanox.com (Ido Schimmel)
petrm@mellanox.com (Petr Machata)
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
        if "rx_prio_stats" in aliases:
            self._rx_prio_stats = aliases["rx_prio_stats"]
        if "tx_prio_stats" in aliases:
            self._tx_prio_stats = aliases["tx_prio_stats"]

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
                                         "iface" : if1.get_devname(),
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

    def iperf_mc_listen(self, listener, mc_group):
        host = listener.get_host()
        srv_m = self._get_iperf_srv_mod(mc_group)
        proc = host.run(srv_m, bg=True, netns=listener.get_netns())
        return proc

    def _get_iperf_cli_mod_packets(self, mc_group, num, speed, size = 100):
        modules_options = {
            "role" : "client",
            "iperf_server" : mc_group,
            "duration" : 1,
            "iperf_opts" : "-u -l %d -n %d -b %dmb -T 100" %
                            (size, size * num, speed)
        }
        return self._ctl.get_module("Iperf", options = modules_options)

    def iperf_mc(self, sender, recivers, mc_group, desc=None):
        if not desc:
            desc = self._generate_default_desc(sender, recivers)

        sender.set_mtu(self._mtu)
        map(lambda i:i.set_mtu(self._mtu), recivers)

        sender_host = sender.get_host()
        recivers_host = map(lambda i:i.get_host(), recivers)

        map(lambda i:i.sync_resources(modules=["Iperf"]),
            recivers_host)

        duration = self._netperf_duration
        speed = self._mc_speed

        # read link-stats
        sender_stats_before = sender.link_stats()
        recivers_stats_before = map(lambda i:i.link_stats(), recivers)

        # An send traffic to all listeners but bridged
        cli_m = self._get_iperf_cli_mod(mc_group, duration, speed)
        sender_host.run(cli_m, timeout=duration + 10, desc=desc,
                        netns=sender.get_netns())

        # re-read link-stats
        sender_stats_after = sender.link_stats()
        recivers_stats_after = map(lambda i:i.link_stats(), recivers)

        # Check that who got multi cast traffic
        tx = sender_stats_after["tx_bytes"] - sender_stats_before["tx_bytes"]
        rx = map(lambda i,l:i["rx_bytes"] - l["rx_bytes"],
                 recivers_stats_after, recivers_stats_before)
        recivers_result = [rate > self._mc_high_thershold for rate in rx]
        for i in zip(rx, recivers):
            logging.info("Measured traffic on %s:%s is %dMb, bytes lost %d (%d%%)" %
                         (i[1].get_host().get_id(), i[1].get_id(),
                          i[0] / 1000000,
                          max(tx - i[0], 0),
                          (max(tx - i[0], 0) * 100) / tx))
        return recivers_result

    def mc_ipref_compare_result(self, ifaces, results, expected):
        err_indices = [i for i in range(len(results))
                       if results[i] != expected[i]]
        for i in err_indices:
            iface, result, expect = ifaces[i], results[i], expected[i]
            err_str = "interface %s in %s %s traffic, when it %s get" % \
                  (iface.get_id(), iface.get_host().get_id(), \
                   ["didn't get", "got"][result], \
                   ["shouldn't", "should"][expect])
            self.custom(iface.get_host(), "iperf_mc", err_str)

    def check_cpu_traffic(self, ifaces, thershold = 100, test = True):
        err = False
        for iface in ifaces:
            stats = iface.link_cpu_ifstat()
            if not test:
                continue

            # Check tx only, since in rx case it is hard to distinguish between
            # offloading error and "legal" cpu traps.
            if stats["tx_packets"] > thershold:
                err = True
                self.custom(iface.get_host(),  "cpu traffic",
                            "%s sent too much data (%d packets)" % \
                            (stats["devname"], stats["tx_packets"]))
        if not err:
            self.custom(iface.get_host(),  "cpu traffic", "")

    def pktgen(self, if1, if2, pkt_size, desc=None, thread_option=[], **kwargs):
        if1.set_mtu(self._mtu)
        m1 = if1.get_host()
        m1.sync_resources(modules=["PktgenTx"])

        pktgen_option = []
        if "count" not in kwargs.keys():
            pktgen_option.append("count 10000")
        if "clone_skb" not in kwargs.keys():
            pktgen_option.append("clone_skb 0")
        if "delay" not in kwargs.keys():
            pktgen_option.append("delay 0")
        if "dst_mac" not in kwargs.keys():
            pktgen_option.append("dst_mac %s" % if2.get_hwaddr())
        pktgen_option.append("pkt_size %s" % pkt_size)
        if "dst" not in kwargs.keys() and "dst_min" not in kwargs.keys() and \
           "dst_max" not in kwargs.keys():
            pktgen_option.append("dst %s" % if2.get_ip(0))
        for arg, argval in kwargs.iteritems():
            if arg == "vlan_id":
                pktgen_option.insert(0, "{} {}".format(arg, argval))
                continue
            pktgen_option.append("{} {}".format(arg, argval))
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

    def check_fdb(self, iface, hwaddr, vlan_id, offload, extern_learn, find=True):
        fdb_table = iface.get_br_fdbs()

        found = False
        err_arg = None
        for fdb in fdb_table:
            if not (fdb["hwaddr"] == str(hwaddr) and fdb["vlan_id"] == vlan_id):
                continue
            if (offload and not fdb["offload"]):
                err_arg = "offload"
                continue
            if (extern_learn and not fdb["extern_learn"]):
                err_arg = "extern_learn"
                continue
            found = True

        if found and not find:
            if err_arg is None:
                err_msg = "didn't find record when should've"
            else:
                err_msg = "found %s record when shouldn't" % err_arg
        elif find and not found:
            err_msg = "didn't find %s record when should've" % err_arg
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

    def get_rx_prio_stats(self, iface, prio):
        stat = "{}{}".format(self._rx_prio_stats, prio)
        return iface.get_ethtool_stats()[stat]

    def get_tx_prio_stats(self, iface, prio):
        stat = "{}{}".format(self._tx_prio_stats, prio)
        return iface.get_ethtool_stats()[stat]

    def check_stats(self, iface, count, expected, desc, fail=False):
        match = count == expected
        err_msg = ""

        if match and fail:
            err_msg = "number of packets matched when shouldn't"
        elif not match and not fail:
            err_msg = "got {} packets, expected {}".format(count, expected)

        return self.custom(iface.get_host(), desc, err_msg)

    def expect_mr_notif(self, sw, notif_type, source_ip = None,
                        source_vif = None, group_ip = None, none_ok = False):
        notif = sw.mroute_get_notif()
        if notif == {}:
            if not none_ok:
                self.custom(sw, "mr_notif", \
                            "No mroute notification - the packet did not arrive to the kernel")
            return None

        if notif["notif_type"] != notif_type:
            self.custom(sw, "mr_notif",
                        "Got notification of wrong type %d != %d" % \
                            (notif_type, notif["notif_type"]))
        if source_ip and notif["source_ip"] != str(source_ip):
            self.custom(sw, "mr_notif",
                        "Got notification with wrong source IP '%s' != '%s'" %
                        (source_ip, notif["source_ip"]))
        if group_ip and notif["group_ip"] != str(group_ip):
            self.custom(sw, "mr_notif",
                        "Got notification with wrong group IP %s != %s" %
                        (group_ip, notif["group_ip"]))
        if source_vif and notif["source_vif"] != source_vif:
            self.custom(sw, "mr_notif",
                        "Got notification with wrong source VIF: %d != %d" % \
                            (source_vif, notif["source_vif"]))
        return notif

class Qdisc:
    def __init__(self, iface, handle, qdisc):
        self._ifname = iface.get_devname()
        self._machine = iface.get_host()
        self._handle = handle
        self.run("tc qdisc add dev %s handle %x: %s"
                 % (self._ifname, self._handle, qdisc))

    def filter_add(self, f):
        self.run("tc filter add dev %s parent %x: %s"
                 % (self._ifname, self._handle, f))

    def flush(self):
        self.run("tc filter del dev %s parent %x:"
                 % (self._ifname, self._handle))

    def run(self, command):
        self._machine.run(command)

class vrf:
    """A context manager that creates a VRF on enter, and destroys it on exit.
    Returns a string name of the newly-allocated VRF. Use with a ``with``
    statement::

        with vrf(machine) as v:
            # Do stuff with v.
            pass
    """

    counter = iter(range(1000))
    def __init__(self, sw):
        """Args:
            sw: The machine to create the VRF on.
        """
        self._id = self.__class__.counter.next()
        self._sw = sw

    def _dev(self):
        return "vrf%d" % self._id

    def __enter__(self):
        tab = 1000 + self._id
        self._sw.run("ip l add name %s type vrf table %d" % (self._dev(), tab))
        self._sw.run("ip l set dev %s up" % self._dev())
        return self._dev()

    def __exit__(self, exc_type, exc_value, traceback):
        self._sw.run("ip l del dev %s" % self._dev())

class dummy:
    """A context manager that creates a dummy device on enter, and destroys it on
    exit. Returns the dummy device created. Use with a ``with`` statement::

        with dummy(machine) as d:
            # Do stuff with d.
            pass
    """

    def __init__(self, sw, vrf_name=None, **kwargs):
        """Args:
            sw: The machine to create the dummy on.
            vrf_name: (Optional) name of VRF to put this device in.
            **kwargs: Arbitrary arguments that are passed to sw.create_dummy.
        """
        self._sw = sw
        self._vrf_name = vrf_name
        self._d_opts = kwargs
        self._d = None

    def _ulfwdroute(self, op):
        self._sw.run("ip r %s tab %d 1.2.3.5/32 via %s"
               % (op, self._vrf_u_tab, ipv4(test_ip(99, 2, []))))

    def __enter__(self):
        self._d = self._sw.create_dummy(**self._d_opts)
        if self._vrf_name is not None:
            self._sw.run("ip l set dev %s master %s"
                         % (self._d.get_devname(), self._vrf_name))
        return self._d

    def __exit__(self, exc_type, exc_value, traceback):
        if self._d is not None:
            self._d.destroy()

class tunnel:
    """A base class for context managers that create tunnel devices on enter, and
    destroy them on exit. Returns the netdevice created. Use with a ``with``
    statement::

        with sometunnel(machine, bound) as t:
            # Do stuff with t.
            pass
    """

    def __init__(self, sw, d, vrf_name=None, **kwargs):
        """Args:
            sw: The machine to create the tunnel on.
            d: A bound device of the tunnel. May be ``None``.
            vrf_name: (Optional) name of VRF to put this device in.
            **kwargs: Arbitrary arguments that are passed to the function that
                creates the tunnel in question, as documented at subclasses.
        """
        self._sw = sw
        self._d = d
        self._vrf_name = vrf_name
        self._opts = kwargs

        self._dev = None

    def _create(self, ul_iface, ip, opts):
        raise NotImplementedError()

    def __enter__(self):
        self._dev = self._create(self._d, self._opts)
        if self._vrf_name is not None:
            self._sw.run("ip link set dev %s vrf %s"
                         % (self._dev.get_devname(), self._vrf_name))

        return self._dev

    def __exit__(self, exc_type, exc_value, traceback):
        if self._dev is not None:
            if self._d is not None:
                self._dev.slave_del(self._d.get_id())
            self._dev.destroy()

class gre(tunnel):
    """A context manager that creates a GRE netdevice on enter and destroys it on
    exit. See ``tunnel`` for more details. This calls ``Task.create_gre`` to
    actually create the tunnel."""
    def _create(self, ul_iface, opts):
        return self._sw.create_gre(ul_iface=ul_iface, **opts)

class ipip(tunnel):
    """A context manager that creates an IPIP netdevice on enter and destroys it on
    exit. See ``tunnel`` for more details. This calls ``Task.create_ipip`` to
    actually create the tunnel."""
    def _create(self, ul_iface, opts):
        return self._sw.create_ipip(ul_iface=ul_iface, **opts)

class route:
    """A context manager that inserts a route on enter and removes it on exit. Use
    with a ``with`` statement::

        with route(machine, vrf, "192.168.2.0/24 via 192.168.1.1"):
            # Test that the router behaves as expected.
            pass
    """

    def __init__(self, sw, vrf_name, route):
        """Args:
            sw: The machine to create the tunnel on.
            vrf_name: Name of VRF to put this device in. May be ``None``.
            route: The route to add.
        """
        self._sw = sw
        self._vrf = vrf_name
        self._route = route

    def do(self, op):
        vrf_arg = " vrf " + self._vrf if self._vrf is not None else ""
        self._sw.run("ip route %s%s %s" % (op, vrf_arg, self._route))

    def __enter__(self):
        self.do("add")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.do("del")
