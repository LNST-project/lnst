#!/bin/python3

import time

from lnst.Common.Parameters import StrParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import Controller
from lnst.Controller import HostReq, DeviceReq

from lnst.Tests.Netperf import Netserver
from lnst.RecipeCommon.TestRecipe import TestRecipe

class SimpleNetperfRecipe(TestRecipe):
    offloads = ["gro", "gso", "tso", "tx"]
    offload_settings = [[("gro", "on"), ("gso", "on"), ("tso", "on"), ("tx", "on"), ("rx", "on")],
                        [("gro", "off"), ("gso", "on"), ("tso", "on"), ("tx", "on"), ("rx", "on")],
                        [("gro", "on"), ("gso", "off"), ("tso", "off"), ("tx", "on"), ("rx", "on")],
                        [("gro", "on"), ("gso", "on"), ("tso", "off"), ("tx", "off"), ("rx", "on")],
                        [("gro", "on"), ("gso", "on"), ("tso", "on"), ("tx", "on"), ("rx", "off")]]

    product_name = StrParam(default="RHEL7")

    m1 = HostReq()
    m1.eth0 = DeviceReq(label="net1")

    m2 = HostReq()
    m2.eth0 = DeviceReq(label="net1")

    def network_setup(self):
        self.matched.m1.eth0.ip_add(ipaddress("192.168.101.1/24"))
        self.matched.m1.eth0.ip_add(ipaddress("fc00::1/64"))
        self.matched.m1.eth0.up()

        self.matched.m2.eth0.ip_add(ipaddress("192.168.101.2/24"))
        self.matched.m2.eth0.ip_add(ipaddress("fc00::2/64"))
        self.matched.m2.eth0.up()

    def clean_setup(self):
        super(SimpleNetperfRecipe, self).clean_setup()
        #reset offload states
        dev_features = ""
        for offload in self.offloads:
            dev_features += " %s %s" % (offload, "on")


        self.matched.m1.run("ethtool -K %s %s" % (self.matched.m1.eth0.name,
                                                  dev_features))
        self.matched.m2.run("ethtool -K %s %s" % (self.matched.m2.eth0.name,
                                                  dev_features))

    def core_test(self):
        ipv = ('ipv4', 'ipv6')
        transport_type = [('tcp', 'TCP_STREAM'), ('udp', 'UDP_STREAM')]

        for setting in self.offload_settings:
            dev_features = ""

            for offload in setting:
                dev_features += " %s %s" % (offload[0], offload[1])

            self.matched.m1.run("ethtool -K %s %s" % (self.matched.m1.eth0.name,
                                                      dev_features))
            self.matched.m2.run("ethtool -K %s %s" % (self.matched.m2.eth0.name,
                                                      dev_features))

            if ("rx", "off") in setting:
                # when rx offload is turned off some of the cards might get reset
                # and link goes down, so wait a few seconds until NIC is ready
                time.sleep(15)


            for ipver in ipv:
                if self.params.ipv in [ipver, 'both']:
                    for ttype, ttype_name in transport_type:
                        ip_num = 0 if ipver is 'ipv4' else 1
                        netperf = self.generate_netperf_cli(self.matched.m1.eth0.ips[ip_num],
                                                            ttype_name)

                        self.netperf_run(Netserver(bind=self.matched.m1.eth0.ips[ip_num]),
                                         netperf)
                        time.sleep(5)


ctl = Controller(debug=1)

r = SimpleNetperfRecipe()
ctl.run(r, allow_virt=True)
