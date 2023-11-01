from lnst.Common.IpAddress import interface_addresses, AF_INET
from lnst.Common.Parameters import IPv4NetworkParam
from lnst.Devices import GeneveDevice
from lnst.Recipes.ENRT.BaseSRIOVNetnsTcRecipe import BaseSRIOVNetnsTcRecipe


class SRIOVNetnsGeneveTcRecipe(
    BaseSRIOVNetnsTcRecipe
):
    """
    This recipe implements Enrt testing for a SRIOV network scenario
    with VF located in the network namespace to mimic container network.
    The traffic between the virtual functions is tunneled through Geneve.
    Tc rules are created to achieve full connectivity between VF of
    the hosts.

    .. code-block:: none

                      +--------+
               +------+ switch +-------+
               |      +--------+       |
       +-------|------+        +-------|------+
       |    +--|--+   |        |    +--|--+   |
    +--|----|eth0|--- |--+  +--|----|eth0|--- |--+
    |  |    +----+    |  |  |  |    +----+    |  |
    |  |      |       |  |  |  |      |       |  |
    |  |    gnv10     |  |  |  |    gnv10     |  |
    |  |      |       |  |  |  |      |       |  |
    |  |vf_representor|  |  |  |vf_representor|  |
    |  |              |  |  |  |              |  |
    |  +--TC filter---+  |  |  +--TC filter---+  |
    |         |          |  |         |          |
    |    +-namespace-+   |  |    +-namespace-+   |
    |   |    vf0     |   |  |   |    vf0     |   |
    |   +-----------+    |  |   +-----------+    |
    |      host1         |  |       host2        |
    +--------------------+  +--------------------+

    All sub configurations are included via Mixin classes.

    The actual test machinery is implemented in the :any:`BaseEnrtRecipe` class.
    """

    tunnel_net_ipv4 = IPv4NetworkParam(default="192.168.200.0/24")

    def add_network_layers(self, config):
        """
        Geneve tunnel is created between PFs on the hosts.
        """

        host1, host2 = self.matched.host1, self.matched.host2

        # TODO: support also IPv6
        tunnel_network = interface_addresses(self.params.tunnel_net_ipv4)
        for host in [host1, host2]:
            config.configure_and_track_ip(host.eth0, next(tunnel_network))

        for host in [host1, host2]:
            # TODO: support also IPv6
            host.gnv10 = GeneveDevice(
                id=10,
                realdev=host.eth0,
                remote=config.ips_for_device(host2.eth0, family=AF_INET)[0] if host == host1 else config.ips_for_device(host1.eth0, family=AF_INET)[0],
                dst_port=6081,
            )

            for dev in [host.newns.vf_eth0, host.vf_representor_eth0]:
                # TODO: support IPv6
                dev.mtu = 1442

            host.gnv10.up()

        self.wait_tentative_ips(config.configured_devices)

    def add_tc_filter_rules(self, config):
        """
        Encapsulation/decapsulation filters are added for ARP an IP traffic.
        """
        host1, host2 = self.matched.host1, self.matched.host2

        config.ingress_devices = []
        # tc configuration
        for host in [host1, host2]:
            host.run(f"tc qdisc add dev {host.eth0.name} ingress")
            host.run(f"tc qdisc add dev {host.vf_representor_eth0.name} ingress")
            host.run(f"tc qdisc add dev {host.gnv10.name} ingress")
            config.ingress_devices.extend([host.eth0, host.vf_representor_eth0, host.gnv10])

        # encap rules
        # host1
        host1.run(
            f"tc filter add dev {host1.vf_representor_eth0.name} protocol ip ingress prio 1 "
            f"flower src_mac {host1.newns.vf_eth0.hwaddr} dst_mac {host2.newns.vf_eth0.hwaddr} "
            f"action tunnel_key set src_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} dst_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} "
            f"dst_port 6081 id 10 "
            f"action mirred egress redirect dev {host1.gnv10.name} "
        )
        host1.run(
            f"tc filter add dev {host1.vf_representor_eth0.name} protocol arp ingress prio 2 "
            f"flower src_mac {host1.newns.vf_eth0.hwaddr} dst_mac {host2.newns.vf_eth0.hwaddr} "
            f"action tunnel_key set src_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} dst_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} "
            f"dst_port 6081 id 10 "
            f"action mirred egress redirect dev {host1.gnv10.name} "
        )
        host1.run(
            f"tc filter add dev {host1.vf_representor_eth0.name} protocol arp ingress prio 3 "
            f"flower src_mac {host1.newns.vf_eth0.hwaddr} dst_mac ff:ff:ff:ff:ff:ff "
            f"action tunnel_key set src_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} dst_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} "
            f"dst_port 6081 id 10 "
            f"action mirred egress redirect dev {host1.gnv10.name} "
        )

        # host2
        host2.run(
            f"tc filter add dev {host2.vf_representor_eth0.name} protocol ip ingress prio 1  "
            f"flower src_mac {host2.newns.vf_eth0.hwaddr} dst_mac {host1.newns.vf_eth0.hwaddr}  "
            f"action tunnel_key set src_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} dst_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} "
            f"dst_port 6081 id 10 "
            f"action mirred egress redirect dev {host2.gnv10.name} "
        )
        host2.run(
            f"tc filter add dev {host2.vf_representor_eth0.name} protocol arp ingress prio 2 "
            f"flower src_mac {host2.newns.vf_eth0.hwaddr} dst_mac {host1.newns.vf_eth0.hwaddr} "
            f"action tunnel_key set src_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} dst_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} "
            f"dst_port 6081 id 10 "
            f"action mirred egress redirect dev {host2.gnv10.name} "
        )
        host2.run(
            f"tc filter add dev {host2.vf_representor_eth0.name} protocol arp ingress prio 3 "
            f"flower src_mac {host2.newns.vf_eth0.hwaddr} dst_mac ff:ff:ff:ff:ff:ff "
            f"action tunnel_key set src_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} dst_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} "
            f"dst_port 6081 id 10 "
            f"action mirred egress redirect dev {host2.gnv10.name} "
        )

        # decap rules
        # host1
        host1.run(
            f"tc filter add dev {host1.gnv10.name} protocol ip ingress prio 1 "
            f"flower src_mac {host2.newns.vf_eth0.hwaddr} dst_mac {host1.newns.vf_eth0.hwaddr} "
            f"enc_src_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} enc_dst_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} "
            f"enc_dst_port 6081 enc_key_id 10 "
            f"action tunnel_key unset "
            f"action mirred egress redirect dev {host1.vf_representor_eth0.name} "
        )
        host1.run(
            f"tc filter add dev {host1.gnv10.name} protocol arp ingress prio 2 "
            f"flower src_mac {host2.newns.vf_eth0.hwaddr} dst_mac {host1.newns.vf_eth0.hwaddr} "
            f"enc_src_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} enc_dst_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} "
            f"enc_dst_port 6081 enc_key_id 10 "
            f"action tunnel_key unset "
            f"action mirred egress redirect dev {host1.vf_representor_eth0.name} "
        )
        host1.run(
            f"tc filter add dev {host1.gnv10.name} protocol arp ingress prio 3 "
            f"flower src_mac {host2.newns.vf_eth0.hwaddr} dst_mac ff:ff:ff:ff:ff:ff "
            f"enc_src_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} enc_dst_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} "
            f"enc_dst_port 6081 enc_key_id 10 "
            f"action tunnel_key unset "
            f"action mirred egress redirect dev {host1.vf_representor_eth0.name} "
        )

        # host2
        host2.run(
            f"tc filter add dev {host2.gnv10.name} protocol ip ingress prio 1 "
            f"flower src_mac {host1.newns.vf_eth0.hwaddr} dst_mac {host2.newns.vf_eth0.hwaddr} "
            f"enc_src_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} enc_dst_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} "
            f"enc_dst_port 6081 enc_key_id 10 "
            f"action tunnel_key unset "
            f"action mirred egress redirect dev {host2.vf_representor_eth0.name} "
        )
        host2.run(
            f"tc filter add dev {host2.gnv10.name} protocol arp ingress prio 2 "
            f"flower src_mac {host1.newns.vf_eth0.hwaddr} dst_mac {host2.newns.vf_eth0.hwaddr} "
            f"enc_src_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} enc_dst_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} "
            f"enc_dst_port 6081 enc_key_id 10 "
            f"action tunnel_key unset "
            f"action mirred egress redirect dev {host2.vf_representor_eth0.name} "
        )
        host2.run(
            f"tc filter add dev {host2.gnv10.name} protocol arp ingress prio 3 "
            f"flower src_mac {host1.newns.vf_eth0.hwaddr} dst_mac ff:ff:ff:ff:ff:ff "
            f"enc_src_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} enc_dst_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} "
            f"enc_dst_port 6081 enc_key_id 10 "
            f"action tunnel_key unset "
            f"action mirred egress redirect dev {host2.vf_representor_eth0.name} "
        )

    @property
    def dump_tc_rules_devices(self):
        return [dev for host in self.matched for dev in [host.gnv10, host.vf_representor_eth0]]

    @property
    def pause_frames_dev_list(self):
        return [self.matched.host1.newns.vf_eth0, self.matched.host2.newns.vf_eth0]

    @property
    def offload_nics(self):
        return [self.matched.host1.newns.vf_eth0, self.matched.host2.newns.vf_eth0]

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.newns.vf_eth0, self.matched.host2.newns.vf_eth0]

    @property
    def coalescing_hw_config_dev_list(self):
        return [self.matched.host1.newns.vf_eth0, self.matched.host2.newns.vf_eth0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.newns.vf_eth0, self.matched.host2.newns.vf_eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.newns.vf_eth0, self.matched.host2.newns.vf_eth0]
