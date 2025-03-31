"""
Module with implementing the XDP forwarding recipe.

Copyright 2025 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
sdobron@redhat.com (Samuel Dobron)
"""


from .ForwardingRecipe import ForwardingRecipe

from lnst.Common.LnstError import LnstError


class XDPForwardingRecipe(ForwardingRecipe):
    """
    Recipe for testing XDP forwarding.

    This recipe requires xdp-forward tool to be installed
    and present in PATH on the forwarding host.

    xdp-forward installation steps are described at
    https://github.com/xdp-project/xdp-tools/tree/main/xdp-forward
    """

    def test_wide_configuration(self, config):
        config = super().test_wide_configuration(config)
        job = self.matched.host2.run(
            f"xdp-forward load {self.forwarder_ingress_nic.name} {self.forwarder_egress_nic.name}"
        )
        if not job.passed:
            raise LnstError(f"Failed to load XDP program: {job.stderr}")

        return config

    def test_wide_deconfiguration(self, config):
        super().test_wide_deconfiguration(config)
        job = self.matched.host2.run(
            f"xdp-forward unload {self.forwarder_ingress_nic.name} {self.forwarder_egress_nic.name}"
        )
        if not job.passed:
            raise LnstError(f"Failed to unload XDP program: {job.stderr}")

        return config
