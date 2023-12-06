from lnst.Common.IpAddress import interface_addresses, AF_INET
from lnst.Common.Parameters import IPv4NetworkParam
from lnst.Devices import VxlanDevice
from lnst.Recipes.ENRT.BaseSRIOVNetnsTcRecipe import BaseSRIOVNetnsTcRecipe


class SRIOVNetnsVxlanTcRecipe(
    BaseSRIOVNetnsTcRecipe
):
    """
    This recipe implements Enrt testing for a SRIOV network scenario
    with VF located in the network namespace to mimic container network.
    The traffic between the virtual functions is tunneled through VXLAN.
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
    |  |    vxlan10   |  |  |  |    vxlan10   |  |
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
        VXLAN tunnel is created between PFs on the hosts.
        """

        host1, host2 = self.matched.host1, self.matched.host2

        # TODO: support also IPv6
        tunnel_network = interface_addresses(self.params.tunnel_net_ipv4)
        for host in [host1, host2]:
            config.configure_and_track_ip(host.eth0, next(tunnel_network))

        for host in [host1, host2]:
            # TODO: support also IPv6
            host.vxlan10 = VxlanDevice(
                vxlan_id=10,
                realdev=host.eth0,
                remote=config.ips_for_device(host2.eth0, family=AF_INET)[0] if host == host1 else config.ips_for_device(host1.eth0, family=AF_INET)[0],
                dst_port=4789,
            )

            for dev in host.sriov_devices[0]:
                # TODO: support IPv6, set to 1430
                dev.mtu = 1450

            host.vxlan10.up()

        self.wait_tentative_ips(config.configured_devices)

    def add_tc_filter_rules(self, config):
        """
        Encapsulation/decapsulation filters are added for ARP an IP traffic.
        """
        host1, host2 = self.matched.host1, self.matched.host2

        config.ingress_devices = []
        # tc configuration
        for host in [host1, host2]:
            vf_representor = host.sriov_devices.vf_reps[0]
            host.run(f"tc qdisc add dev {host.eth0.name} ingress")
            host.run(f"tc qdisc add dev {vf_representor.name} ingress")
            host.run(f"tc qdisc add dev {host.vxlan10.name} ingress")
            config.ingress_devices.extend([host.eth0, vf_representor, host.vxlan10])

        host1_vf_dev, host1_vf_rep_dev = host1.sriov_devices[0]
        host2_vf_dev, host2_vf_rep_dev = host2.sriov_devices[0]

        # encap rules
        # host1
        host1.run(
            f"tc filter add dev {host1_vf_rep_dev.name} protocol ip ingress prio 1 "
            f"flower src_mac {host1_vf_dev.hwaddr} dst_mac {host2_vf_dev.hwaddr} "
            f"action tunnel_key set src_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} dst_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} "
            f"dst_port 4789 id 10 "
            f"action mirred egress redirect dev {host1.vxlan10.name} "
        )
        host1.run(
            f"tc filter add dev {host1_vf_rep_dev.name} protocol arp ingress prio 2 "
            f"flower src_mac {host1_vf_dev.hwaddr} dst_mac {host2_vf_dev.hwaddr} "
            f"action tunnel_key set src_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} dst_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} "
            f"dst_port 4789 id 10 "
            f"action mirred egress redirect dev {host1.vxlan10.name} "
        )
        host1.run(
            f"tc filter add dev {host1_vf_rep_dev.name} protocol arp ingress prio 3 "
            f"flower src_mac {host1_vf_dev.hwaddr} dst_mac ff:ff:ff:ff:ff:ff "
            f"action tunnel_key set src_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} dst_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} "
            f"dst_port 4789 id 10 "
            f"action mirred egress redirect dev {host1.vxlan10.name} "
        )

        # host2
        host2.run(
            f"tc filter add dev {host2_vf_rep_dev.name} protocol ip ingress prio 1  "
            f"flower src_mac {host2_vf_dev.hwaddr} dst_mac {host1_vf_dev.hwaddr}  "
            f"action tunnel_key set src_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} dst_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} "
            f"dst_port 4789 id 10 "
            f"action mirred egress redirect dev {host2.vxlan10.name} "
        )
        host2.run(
            f"tc filter add dev {host2_vf_rep_dev.name} protocol arp ingress prio 2 "
            f"flower src_mac {host2_vf_dev.hwaddr} dst_mac {host1_vf_dev.hwaddr} "
            f"action tunnel_key set src_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} dst_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} "
            f"dst_port 4789 id 10 "
            f"action mirred egress redirect dev {host2.vxlan10.name} "
        )
        host2.run(
            f"tc filter add dev {host2_vf_rep_dev.name} protocol arp ingress prio 3 "
            f"flower src_mac {host2_vf_dev.hwaddr} dst_mac ff:ff:ff:ff:ff:ff "
            f"action tunnel_key set src_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} dst_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} "
            f"dst_port 4789 id 10 "
            f"action mirred egress redirect dev {host2.vxlan10.name} "
        )

        # decap rules
        # host1
        host1.run(
            f"tc filter add dev {host1.vxlan10.name} protocol ip ingress prio 1 "
            f"flower src_mac {host2_vf_dev.hwaddr} dst_mac {host1_vf_dev.hwaddr} "
            f"enc_src_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} enc_dst_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} "
            f"enc_dst_port 4789 enc_key_id 10 "
            f"action tunnel_key unset "
            f"action mirred egress redirect dev {host1_vf_rep_dev.name} "
        )
        host1.run(
            f"tc filter add dev {host1.vxlan10.name} protocol arp ingress prio 2 "
            f"flower src_mac {host2_vf_dev.hwaddr} dst_mac {host1_vf_dev.hwaddr} "
            f"enc_src_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} enc_dst_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} "
            f"enc_dst_port 4789 enc_key_id 10 "
            f"action tunnel_key unset "
            f"action mirred egress redirect dev {host1_vf_rep_dev.name} "
        )
        host1.run(
            f"tc filter add dev {host1.vxlan10.name} protocol arp ingress prio 3 "
            f"flower src_mac {host2_vf_dev.hwaddr} dst_mac ff:ff:ff:ff:ff:ff "
            f"enc_src_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} enc_dst_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} "
            f"enc_dst_port 4789 enc_key_id 10 "
            f"action tunnel_key unset "
            f"action mirred egress redirect dev {host1_vf_rep_dev.name} "
        )

        # host2
        host2.run(
            f"tc filter add dev {host2.vxlan10.name} protocol ip ingress prio 1 "
            f"flower src_mac {host1_vf_dev.hwaddr} dst_mac {host2_vf_dev.hwaddr} "
            f"enc_src_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} enc_dst_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} "
            f"enc_dst_port 4789 enc_key_id 10 "
            f"action tunnel_key unset "
            f"action mirred egress redirect dev {host2_vf_rep_dev.name} "
        )
        host2.run(
            f"tc filter add dev {host2.vxlan10.name} protocol arp ingress prio 2 "
            f"flower src_mac {host1_vf_dev.hwaddr} dst_mac {host2_vf_dev.hwaddr} "
            f"enc_src_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} enc_dst_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} "
            f"enc_dst_port 4789 enc_key_id 10 "
            f"action tunnel_key unset "
            f"action mirred egress redirect dev {host2_vf_rep_dev.name} "
        )
        host2.run(
            f"tc filter add dev {host2.vxlan10.name} protocol arp ingress prio 3 "
            f"flower src_mac {host1_vf_dev.hwaddr} dst_mac ff:ff:ff:ff:ff:ff "
            f"enc_src_ip {config.ips_for_device(host1.eth0, family=AF_INET)[0]} enc_dst_ip {config.ips_for_device(host2.eth0, family=AF_INET)[0]} "
            f"enc_dst_port 4789 enc_key_id 10 "
            f"action tunnel_key unset "
            f"action mirred egress redirect dev {host2_vf_rep_dev.name} "
        )

    @property
    def dump_tc_rules_devices(self):
        return [dev for host in self.matched for dev in [host.vxlan10, host.sriov_devices.vf_reps[0]]]

    @property
    def pause_frames_dev_list(self):
        return [self.matched.host1.sriov_devices.vfs[0], self.matched.host2.sriov_devices.vfs[0]]

    @property
    def offload_nics(self):
        return [self.matched.host1.sriov_devices.vfs[0], self.matched.host2.sriov_devices.vfs[0]]

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.sriov_devices.vfs[0], self.matched.host2.sriov_devices.vfs[0]]

    @property
    def coalescing_hw_config_dev_list(self):
        return [self.matched.host1.sriov_devices.vfs[0], self.matched.host2.sriov_devices.vfs[0]]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.sriov_devices.vfs[0], self.matched.host2.sriov_devices.vfs[0]]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.sriov_devices.vfs[0], self.matched.host2.sriov_devices.vfs[0]]
