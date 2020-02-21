#!/bin/python3

import time
import re

from lnst.Common.Parameters import StrParam, IntParam, Param
from lnst.Controller import BaseRecipe
from lnst.Controller.Recipe import RecipeError

from lnst.Tests.Netperf import Netperf

from lnst.RecipeCommon.IRQ import pin_dev_irqs

class TestRecipe(BaseRecipe):
    ipv = StrParam(default="both")
    mtu = IntParam(default=1500)

    nperf_cpupin = IntParam()
    nperf_reserve = IntParam(default=20)
    nperf_mode = StrParam(default="default")

    netperf_duration = IntParam(default=1)
    netperf_confidence = StrParam(default="99,5")
    netperf_runs = IntParam(default=5)
    netperf_cpu_util = IntParam()
    netperf_num_parallel = IntParam(default=2)
    netperf_debug = IntParam(default=0)
    netperf_max_deviation = Param(default={
                        'type': 'percent',
                        'value': 20})

    test_if1 = Param()
    test_if2 = Param()

    def __init__(self, **kwargs):
        super(TestRecipe, self).__init__(**kwargs)

    def initial_setup(self):
        machines = []

        if "nperf_cpupin" in self.params:
            for m in self.matched:
                m.run("service irqbalance stop")

            for m in self.matched:
                for d in m.devices:
                    if re.match(r'^eth[0-9]+$', d.name):
                        pin_dev_irqs(m, d, 0)


        self.nperf_opts = ""

        if "test_if2" in self.params:
            self.nperf_opts = "-L %s" % (self.params.test_if2.ips[0])

        if "nperf_cpupin" in self.params and self.params.netperf_mode != "multi":
            self.nperf_opts += " -T%s,%s" % (self.params.netperf_cpupin,
                                    self.params.netperf_cpupin)

        self.nperf_opts6 = ""

        if "test_if2" in self.params:
            self.nperf_opts6 = "-L %s" % (self.params.test_if2.ips[1])

        self.nperf_opts6 += " -6"

        if "nperf_cpupin" in self.params and self.params.netperf_mode != "multi":
            self.nperf_popts6 += " -T%s,%s" % (self.params.netperf_cpupin,
                                     self.params.netperf_cpupin)

        time.sleep(15)

    def clean_setup(self):
        if "nperf_cpupin" in self.params:
            for m in self.matched:
                m.run("service irqbalance start")

    def generate_netperf_cli(self, dst_addr, testname):
        kwargs = {}

        for key, val in self.params:
            param_name = re.split(r'netperf_', key)
            if len(param_name) > 1:
                kwargs[param_name[1]] = val

        kwargs['server'] = dst_addr
        kwargs['testname'] = testname

        if str(dst_addr).find(":") is -1:
            kwargs['opts'] = self.nperf_opts
        else:
            kwargs['opts'] = self.nperf_opts6

        return Netperf(**kwargs)


    def netperf_run(self, netserver, netperf):
        srv_proc = self.matched.m1.run(netserver, bg=True)

        time.sleep(2)

        res_data = self.matched.m2.run(netperf,
                                       timeout = (
                                       self.params.netperf_duration +
                                       self.params.nperf_reserve) *
                                       self.params.netperf_runs)

        srv_proc.kill(2)

        return res_data, srv_proc

    def network_setup(self):
        pass

    def core_test(self):
        pass

    def test(self):
        self.network_setup()
        self.initial_setup()
        self.core_test()
        self.clean_setup()
