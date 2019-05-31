"""
Implements scenario similar to regression_tests/phase3/
(simple_macsec.xml + simple_macsec.py)
"""
import logging
from lnst.Common.IpAddress import ipaddress
from lnst.Common.IpAddress import AF_INET, AF_INET6
from lnst.Common.LnstError import LnstError
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Devices import MacsecDevice
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration, EnrtSubConfiguration
from lnst.RecipeCommon.Perf.Recipe import RecipeConf as PerfRecipeConf
from lnst.RecipeCommon.Perf.Measurements import Flow as PerfFlow
from lnst.RecipeCommon.Ping import PingConf

class MacsecEnrtConfiguration(EnrtConfiguration):
    def __init__(self):
        super(MacsecEnrtConfiguration, self).__init__()
        self._host1 = None
        self._host2 = None

    @property
    def host1(self):
        return self._host1

    @host1.setter
    def host1(self, value):
        self._host1 = value

    @property
    def host2(self):
        return self._host2

    @host2.setter
    def host2(self, value):
        self._host2 = value

class MacsecEnrtSubConfiguration(EnrtSubConfiguration):
    def __init__(self):
        super(MacsecEnrtSubConfiguration, self).__init__()
        self._ip_vers = ('ipv4',)
        self._encrypt = None

    @property
    def encrypt(self):
        return self._encrypt

    @encrypt.setter
    def encrypt(self, value):
        self._encrypt = value

    @property
    def ip_vers(self):
        return self._ip_vers

    @ip_vers.setter
    def ip_vers(self, value):
        self._ip_vers = value

class SimpleMacsecRecipe(BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    macsec_settings = [None, 'on', 'off']
    ids = ['00', '01']
    keys = ["7a16780284000775d4f0a3c0f0e092c0", "3212ef5c4cc5d0e4210b17208e88779e"]

    def test_wide_configuration(self):
        host1, host2 = self.matched.host1, self.matched.host2

        for host in [host1, host2]:
            host.eth0.down()

        net_addr = "192.168.0"

        for i, host in enumerate([host1, host2]):
            host.eth0.ip_add(ipaddress(net_addr + '.' + str(i+1) + "/24"))

        #Due to limitations in the current EnrtConfiguration
        #class, a single test pair is chosen
        configuration = EnrtConfiguration()
        configuration.endpoint1 = host1.eth0
        configuration.endpoint2 = host2.eth0
        configuration.host1 = host1
        configuration.host2 = host2

        if (self.params.ping_parallel or self.params.ping_bidirect or
            self.params.perf_reverse):
            logging.debug("Parallelism in pings or reverse perf tests are "
                          "not supported for this recipe, ping_parallel/bidirect "
                          " or perf_reverse will be ignored.")

        if "mtu" in self.params:
            for host in [host1, host2]:
                host.eth0.mtu = self.params.mtu

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for host in [host1, host2]:
                host.run("service irqbalance stop")
                self._pin_dev_interrupts(host.eth0, self.params.dev_intr_cpu)

        return configuration

    def test_wide_deconfiguration(self, config):
        host1, host2 = self.matched.host1, self.matched.host2

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for host in [host1, host2]:
                host.run("service irqbalance start")

    def generate_sub_configurations(self, main_config):
        for encryption in self.macsec_settings:
            sub_config = MacsecEnrtSubConfiguration()
            sub_config.encrypt = encryption
            if encryption is not None:
                sub_config.ip_vers = self.params.ip_versions
            yield sub_config

    def apply_sub_configuration(self, main_config, sub_config):
        if not sub_config.encrypt:
            main_config.endpoint1.up()
            main_config.endpoint2.up()
        else:
            net_addr = "192.168.100"
            net_addr6 = "fc00:0:0:0"
            host1, host2 = main_config.host1, main_config.host2
            k_ids = zip(self.ids, self.keys)
            hosts_and_keys = [(host1, host2, k_ids), (host2, host1, k_ids[::-1])]
            for host_a, host_b, k_ids in hosts_and_keys:
                host_a.msec0 = MacsecDevice(realdev=host_a.eth0, encrypt=sub_config.encrypt)
                rx_kwargs = dict(port=1, address=host_b.eth0.hwaddr)
                tx_sa_kwargs = dict(sa=0, pn=1, enable='on', id=k_ids[0][0], key=k_ids[0][1])
                rx_sa_kwargs = rx_kwargs.copy()
                rx_sa_kwargs.update(tx_sa_kwargs)
                rx_sa_kwargs['id'] = k_ids[1][0]
                rx_sa_kwargs['key'] = k_ids[1][1]
                host_a.msec0.rx('add', **rx_kwargs)
                host_a.msec0.tx_sa('add', **tx_sa_kwargs)
                host_a.msec0.rx_sa('add', **rx_sa_kwargs)
            for i, host in enumerate([host1, host2]):
                host.msec0.ip_add(ipaddress(net_addr + "." + str(i+1) + "/24"))
                host.msec0.ip_add(ipaddress(net_addr6 + "::" + str(i+1) + "/64"))
                host.eth0.up()
                host.msec0.up()

    def remove_sub_configuration(self, main_config, sub_config):
        if sub_config.encrypt:
            host1, host2 = main_config.host1, main_config.host2
            for host in (host1, host2):
                host.msec0.destroy()
                del host.msec0
        main_config.endpoint1.down()
        main_config.endpoint2.down()

    def generate_ping_configurations(self, main_config, sub_config):
        if not sub_config.encrypt:
            client_nic = main_config.endpoint1
            server_nic = main_config.endpoint2
            ip_vers = ('ipv4',)
        else:
            client_nic = main_config.host1.msec0
            server_nic = main_config.host2.msec0
            ip_vers = self.params.ip_versions

        count = self.params.ping_count
        interval = self.params.ping_interval
        size = self.params.ping_psize
        common_args = {'count' : count, 'interval' : interval, 'size' : size}

        for ipv in ip_vers:
            kwargs = {}
            if ipv == "ipv4":
                kwargs.update(family = AF_INET)
            elif ipv == "ipv6":
                kwargs.update(family = AF_INET6)
                kwargs.update(is_link_local = False)

            client_ips = client_nic.ips_filter(**kwargs)
            server_ips = server_nic.ips_filter(**kwargs)
            if ipv == "ipv6":
                client_ips = client_ips[::-1]
                server_ips = server_ips[::-1]

            if len(client_ips) != len(server_ips) or len(client_ips) * len(server_ips) == 0:
                raise LnstError("Source/destination ip lists are of different size or empty.")

            for src_addr, dst_addr in zip(client_ips, server_ips):
                pconf = PingConf(client = client_nic.netns,
                                 client_bind = src_addr,
                                 destination = server_nic.netns,
                                 destination_address = dst_addr,
                                 **common_args)

                yield [pconf]

    def generate_perf_configurations(self, main_config, sub_config):
        if sub_config.encrypt:
            client_nic = main_config.host1.msec0
            server_nic = main_config.host2.msec0
            client_netns = client_nic.netns
            server_netns = server_nic.netns

            flow_combinations = self.generate_flow_combinations(
                main_config, sub_config
            )

            for flows in flow_combinations:
                perf_recipe_conf=dict(
                    main_config=main_config,
                    sub_config=sub_config,
                    flows=flows,
                )

                flows_measurement = self.params.net_perf_tool(
                    flows,
                    perf_recipe_conf
                )

                cpu_measurement = self.params.cpu_perf_tool(
                    [client_netns, server_netns],
                    perf_recipe_conf,
                )

                perf_conf = PerfRecipeConf(
                    measurements=[cpu_measurement, flows_measurement],
                    iterations=self.params.perf_iterations,
                )

                perf_conf.register_evaluators(
                    cpu_measurement, self.cpu_perf_evaluators
                )
                perf_conf.register_evaluators(
                    flows_measurement, self.net_perf_evaluators
                )

                yield perf_conf

    def generate_flow_combinations(self, main_config, sub_config):
        client_nic = main_config.host1.msec0
        server_nic = main_config.host2.msec0
        client_netns = client_nic.netns
        server_netns = server_nic.netns

        for ipv in self.params.ip_versions:
            if ipv == "ipv4":
                family = AF_INET
            elif ipv == "ipv6":
                family = AF_INET6

            client_bind = client_nic.ips_filter(family=family)[0]
            server_bind = server_nic.ips_filter(family=family)[0]

            for perf_test in self.params.perf_tests:
                for size in self.params.perf_msg_sizes:
                    flow = PerfFlow(
                            type = perf_test,
                            generator = client_netns,
                            generator_bind = client_bind,
                            receiver = server_netns,
                            receiver_bind = server_bind,
                            msg_size = size,
                            duration = self.params.perf_duration,
                            parallel_streams = self.params.perf_parallel_streams,
                            cpupin = self.params.perf_tool_cpu if "perf_tool_cpu" in self.params else None
                            )
                    yield [flow]
