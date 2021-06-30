#!/bin/python3
"""
This is an example python recipe that can be run as an executable script.
Performs a simple ping between two hosts.
"""

import logging
from lnst.Common.Parameters import IpParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import Controller
from lnst.Controller import BaseRecipe
from lnst.Controller import HostReq, DeviceReq

from lnst.Devices import BondDevice
from lnst.Devices import BridgeDevice
from lnst.Devices import TeamDevice
from lnst.Devices import MacvlanDevice
from lnst.Devices import VethPair
from lnst.Devices import VlanDevice
from lnst.Devices import VtiDevice
from lnst.Devices import VxlanDevice

from lnst.Tests import Ping
from lnst.Tests.Netperf import Netperf, Netserver

import signal


from lnst.Controller.RunSummaryFormatter import RunSummaryFormatter

class MyRecipe(BaseRecipe):
    m1 = HostReq()
    m1.eth0 = DeviceReq(label="net1")

    m2 = HostReq()
    m2.eth0 = DeviceReq(label="net1")

    def test(self):
        self.matched.m1.eth0.ip_add(ipaddress("192.168.1.1/24"))
        self.matched.m1.eth0.up()
        self.matched.m2.eth0.ip_add(ipaddress("192.168.1.2/24"))
        self.matched.m2.eth0.up()
        ping_job = self.matched.m1.run(Ping(dst=self.matched.m2.eth0,
                                                interval=0,
                                                iface=self.matched.m1.eth0))

        netserver_job = self.matched.m1.run(Netserver(bind=self.matched.m1.eth0),
                                            bg=True)

        netperf_job = self.matched.m2.run(Netperf(server=self.matched.m1.eth0,
                                                  duration=1,
                                                  confidence="99,5",
                                                  runs="5",
                                                  debug=0,
                                                  max_deviation={'type':"percent",
                                                                 'value':20.0},
                                                  testname="TCP_STREAM"))

        netserver_job.kill(signal=signal.SIGINT)

        #examples of how to create soft devices
        self.matched.m1.eth0.down()

        m1 = self.matched.m1
        eth0 = m1.eth0

        #Bonding
        m1.bond = BondDevice(mode="active-backup", name="my_bond0")
        m1.bond.slave_add(eth0)
        m1.bond.up()
        m1.run("ip a")
        m1.bond.destroy()

        #Bridging
        m1.br = BridgeDevice()
        m1.br.slave_add(eth0)
        m1.br.up()
        m1.run("ip a")
        m1.br.destroy()

        #Teaming
        m1.team = TeamDevice()
        m1.team.slave_add(eth0)
        m1.team.up()
        m1.run("ip a")
        m1.team.destroy()

        #VethPair
        m1.veth0, m1.veth1 = VethPair()
        m1.veth0.up()
        m1.veth1.up()
        m1.run("ip a")
        m1.veth0.destroy()

        #Macvlan
        m1.mvlan = MacvlanDevice(realdev=eth0)
        m1.mvlan.up()
        m1.run("ip a")
        m1.mvlan.destroy()

        #Vlan
        eth0.up()
        m1.vlan = VlanDevice(realdev=eth0, vlan_id=123)
        m1.vlan.up()
        m1.run("ip a")
        m1.vlan.destroy()
        eth0.down()

        #Vti
        m1.vti = VtiDevice(local="1.2.3.4", ikey=123, okey=321)
        m1.vti.up()
        m1.run("ip a")
        m1.vti.destroy()

        #Vxlan
        m1.vxlan0 = VxlanDevice(vxlan_id=123, remote='1.2.3.4')
        m1.vxlan0.up()
        self.matched.m1.run("ip a")
        m1.vxlan0.destroy()

ctl = Controller(debug=1)

r = MyRecipe()
ctl.run(r, allow_virt=True)

summary_fmt = RunSummaryFormatter()
for run in r.runs:
    logging.info(summary_fmt.format_run(run))
