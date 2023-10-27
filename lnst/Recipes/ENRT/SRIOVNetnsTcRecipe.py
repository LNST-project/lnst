from lnst.Recipes.ENRT.BaseSRIOVNetnsTcRecipe import BaseSRIOVNetnsTcRecipe


class SRIOVNetnsTcRecipe(BaseSRIOVNetnsTcRecipe):
    """
    This recipe implements Enrt testing for a SRIOV network scenario
    with VF located in the network namespace to mimic container network.
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
    |  |       |      |  |  |  |       |      |  |
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
    def add_tc_filter_rules(self, config):
        host1, host2 = self.matched.host1, self.matched.host2

        config.ingress_devices = []
        for host in [host1, host2]:
            host.run(f"tc qdisc add dev {host.vf_representor_eth0.name} ingress")
            host.run(f"tc qdisc add dev {host.eth0.name} ingress")
            config.ingress_devices.extend([host.vf_representor_eth0, host.eth0])

        host1.run(f"tc filter add dev {host1.eth0.name} "
                  f"protocol ip ingress flower skip_sw "
                  f"src_mac {host2.newns.vf_eth0.hwaddr} "
                  f"dst_mac {host1.newns.vf_eth0.hwaddr} "
                  f"action mirred egress redirect dev {host1.vf_representor_eth0.name}")

        host1.run(f"tc filter add dev {host1.eth0.name} "
                  f"protocol arp ingress flower "
                  f"src_mac {host2.newns.vf_eth0.hwaddr} "
                  f"dst_mac {host1.newns.vf_eth0.hwaddr} "
                  f"action mirred egress redirect dev {host1.vf_representor_eth0.name}")

        host1.run(f"tc filter add dev {host1.eth0.name} "
                  f"protocol arp ingress flower "
                  f"src_mac {host2.newns.vf_eth0.hwaddr} "
                  f"dst_mac FF:FF:FF:FF:FF:FF "
                  f"action mirred egress redirect dev {host1.vf_representor_eth0.name}")

        host1.run(f"tc filter add dev {host1.vf_representor_eth0.name} "
                  f"protocol ip ingress flower skip_sw "
                  f"src_mac {host1.newns.vf_eth0.hwaddr} "
                  f"dst_mac {host2.newns.vf_eth0.hwaddr} "
                  f"action mirred egress redirect dev {host1.eth0.name}")

        host1.run(f"tc filter add dev {host1.vf_representor_eth0.name} "
                  f"protocol arp ingress flower "
                  f"src_mac {host1.newns.vf_eth0.hwaddr} "
                  f"dst_mac {host2.newns.vf_eth0.hwaddr} "
                  f"action mirred egress redirect dev {host1.eth0.name}")

        host1.run(f"tc filter add dev {host1.vf_representor_eth0.name} "
                  f"protocol arp ingress flower "
                  f"src_mac {host1.newns.vf_eth0.hwaddr} "
                  f"dst_mac FF:FF:FF:FF:FF:FF "
                  f"action mirred egress redirect dev {host1.eth0.name}")

        host2.run(f"tc filter add dev {host2.eth0.name} "
                  f"protocol ip ingress flower skip_sw "
                  f"src_mac {host1.newns.vf_eth0.hwaddr} "
                  f"dst_mac {host2.newns.vf_eth0.hwaddr} "
                  f"action mirred egress redirect dev {host2.vf_representor_eth0.name}")

        host2.run(f"tc filter add dev {host2.eth0.name} "
                  f"protocol arp ingress flower "
                  f"src_mac {host1.newns.vf_eth0.hwaddr} "
                  f"dst_mac {host2.newns.vf_eth0.hwaddr} "
                  f"action mirred egress redirect dev {host2.vf_representor_eth0.name}")

        host2.run(f"tc filter add dev {host2.eth0.name} "
                  f"protocol arp ingress flower "
                  f"src_mac {host1.newns.vf_eth0.hwaddr} "
                  f"dst_mac FF:FF:FF:FF:FF:FF "
                  f"action mirred egress redirect dev {host2.vf_representor_eth0.name}")

        host2.run(f"tc filter add dev {host2.vf_representor_eth0.name} "
                  f"protocol ip ingress flower skip_sw "
                  f"src_mac {host2.newns.vf_eth0.hwaddr} "
                  f"dst_mac {host1.newns.vf_eth0.hwaddr} "
                  f"action mirred egress redirect dev {host2.eth0.name}")

        host2.run(f"tc filter add dev {host2.vf_representor_eth0.name} "
                  f"protocol arp ingress flower "
                  f"src_mac {host2.newns.vf_eth0.hwaddr} "
                  f"dst_mac {host1.newns.vf_eth0.hwaddr} "
                  f"action mirred egress redirect dev {host2.eth0.name}")

        host2.run(f"tc filter add dev {host2.vf_representor_eth0.name} "
                  f"protocol arp ingress flower "
                  f"src_mac {host2.newns.vf_eth0.hwaddr} "
                  f"dst_mac FF:FF:FF:FF:FF:FF "
                  f"action mirred egress redirect dev {host2.eth0.name}")

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
