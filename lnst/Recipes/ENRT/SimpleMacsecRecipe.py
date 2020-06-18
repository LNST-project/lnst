import logging
import copy
from lnst.Common.IpAddress import ipaddress
from lnst.Common.IpAddress import AF_INET, AF_INET6
from lnst.Common.LnstError import LnstError
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Devices import MacsecDevice
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.BaseSubConfigMixin import (
    BaseSubConfigMixin as ConfMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.RecipeCommon.Perf.Recipe import RecipeConf as PerfRecipeConf
from lnst.RecipeCommon.Perf.Measurements import Flow as PerfFlow
from lnst.RecipeCommon.Ping.Recipe import PingConf

class SimpleMacsecRecipe(CommonHWSubConfigMixin, BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    macsec_settings = [None, 'on', 'off']
    ids = ['00', '01']
    keys = ["7a16780284000775d4f0a3c0f0e092c0",
        "3212ef5c4cc5d0e4210b17208e88779e"]

    def test_wide_configuration(self):
        host1, host2 = self.matched.host1, self.matched.host2

        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = [host1.eth0, host2.eth0]

        net_addr = "192.168.0"
        for i, host in enumerate([host1, host2]):
            host.eth0.down()
            host.eth0.ip_add(ipaddress(net_addr + '.' + str(i+1) + "/24"))

        self.wait_tentative_ips(configuration.test_wide_devices)

        configuration.endpoint1 = host1.eth0
        configuration.endpoint2 = host2.eth0
        configuration.host1 = host1
        configuration.host2 = host2

        return configuration

    def generate_test_wide_description(self, config):
        host1, host2 = self.matched.host1, self.matched.host2
        desc = super().generate_test_wide_description(config)
        desc += [
            "\n".join([
                "Configured {}.{}.ips = {}".format(
                    dev.host.hostid, dev.name, dev.ips
                )
                for dev in config.test_wide_devices
            ])
        ]
        return desc

    def test_wide_deconfiguration(self, config):
        del config.test_wide_devices

        super().test_wide_deconfiguration(config)

    def generate_sub_configurations(self, config):
        for subconf in ConfMixin.generate_sub_configurations(self, config):
            for encryption in self.macsec_settings:
                new_config = copy.copy(subconf)
                new_config.encrypt = encryption
                if encryption is not None:
                    new_config.ip_vers = self.params.ip_versions
                yield new_config

    def apply_sub_configuration(self, config):
        super().apply_sub_configuration(config)
        if not config.encrypt:
            config.endpoint1.up()
            config.endpoint2.up()
        else:
            net_addr = "192.168.100"
            net_addr6 = "fc00:0:0:0"
            host1, host2 = config.host1, config.host2
            k_ids = list(zip(self.ids, self.keys))
            hosts_and_keys = [(host1, host2, k_ids), (host2, host1,
                k_ids[::-1])]
            for host_a, host_b, k_ids in hosts_and_keys:
                host_a.msec0 = MacsecDevice(realdev=host_a.eth0,
                    encrypt=config.encrypt)
                rx_kwargs = dict(port=1, address=host_b.eth0.hwaddr)
                tx_sa_kwargs = dict(sa=0, pn=1, enable='on',
                    id=k_ids[0][0], key=k_ids[0][1])
                rx_sa_kwargs = rx_kwargs.copy()
                rx_sa_kwargs.update(tx_sa_kwargs)
                rx_sa_kwargs['id'] = k_ids[1][0]
                rx_sa_kwargs['key'] = k_ids[1][1]
                host_a.msec0.rx('add', **rx_kwargs)
                host_a.msec0.tx_sa('add', **tx_sa_kwargs)
                host_a.msec0.rx_sa('add', **rx_sa_kwargs)
            for i, host in enumerate([host1, host2]):
                host.msec0.ip_add(ipaddress(net_addr + "." + str(i+1) +
                    "/24"))
                host.msec0.ip_add(ipaddress(net_addr6 + "::" + str(i+1) +
                    "/64"))
                host.eth0.up()
                host.msec0.up()

    def remove_sub_configuration(self, config):
        if config.encrypt:
            host1, host2 = config.host1, config.host2
            for host in (host1, host2):
                host.msec0.destroy()
                del host.msec0
        config.endpoint1.down()
        config.endpoint2.down()
        super().remove_sub_configuration(config)

    def generate_ping_configurations(self, config):
        if not config.encrypt:
            client_nic = config.endpoint1
            server_nic = config.endpoint2
            ip_vers = ('ipv4',)
        else:
            client_nic = config.host1.msec0
            server_nic = config.host2.msec0
            ip_vers = self.params.ip_versions

        count = self.params.ping_count
        interval = self.params.ping_interval
        size = self.params.ping_psize
        common_args = {'count' : count, 'interval' : interval,
            'size' : size}

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

            if len(client_ips) != len(server_ips) or (len(client_ips) *
                len(server_ips) == 0):
                raise LnstError("Source/destination ip lists are of "
                    "different size or empty.")

            for src_addr, dst_addr in zip(client_ips, server_ips):
                pconf = PingConf(client = client_nic.netns,
                                 client_bind = src_addr,
                                 destination = server_nic.netns,
                                 destination_address = dst_addr,
                                 **common_args)

                yield [pconf]

    def generate_perf_configurations(self, config):
        if config.encrypt:
            client_nic = config.host1.msec0
            server_nic = config.host2.msec0
            client_netns = client_nic.netns
            server_netns = server_nic.netns

            flow_combinations = self.generate_flow_combinations(
                config
            )

            for flows in flow_combinations:
                perf_recipe_conf=dict(
                    recipe_config=config,
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

    def generate_flow_combinations(self, config):
        client_nic = config.host1.msec0
        server_nic = config.host2.msec0
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
                    pstreams = self.params.perf_parallel_streams
                    flow = PerfFlow(
                        type = perf_test,
                        generator = client_netns,
                        generator_bind = client_bind,
                        receiver = server_netns,
                        receiver_bind = server_bind,
                        msg_size = size,
                        duration = self.params.perf_duration,
                        parallel_streams = pstreams,
                        cpupin = self.params.perf_tool_cpu if (
                            "perf_tool_cpu" in self.params) else None
                            )
                    yield [flow]

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
