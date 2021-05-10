"""
This module defines the L2TPManager class that provides an API for
creating and deleting L2TP tunnels. It uses pyroute2 API for the tunnel
management.

Copyright 2021 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jtluka@redhat.com (Jan Tluka)
"""

import logging
from pyroute2.netlink import NetlinkError
from pyroute2.netlink.generic.l2tp import L2tp
from lnst.Common.LnstError import LnstError


class L2tpConfigurationError(LnstError):
    pass


class L2tpDeconfigurationError(LnstError):
    pass


class L2TPManager:
    """
    This class serves as an LNST interface to create the L2TP tunnels in an
    LNST recipe.

    Users should use the :meth:`Host.init_class` method to create a host
    specific instance of the class as shown in the following example:

    .. code-block:: python

        from lnst.Controller import BaseRecipe
        from lnst.Controller.Requirements import HostReq
        from lnst.RecipeCommon.L2TPManager import L2TPManager

        class L2TPRecipe(BaseRecipe):
            m1 = HostReq()

            def test(self):
                m1 = self.matched.m1
                m1.l2tp = m1.init_class(L2TPManager)

    This class provides only the API to create and destroy the L2TP tunnels.
    To create a session for an L2TP tunnel you have to use the
    :any:`L2TPSessionDevice`.

    LNST will not cleanup any of the tunnels created in a recipe, so it is
    user's responsibility to delete all previously created tunnels. This
    applies also to situation when an exception is raised during the recipe
    execution.

    This can be handled by a code similar to the following:

    .. code-block:: python

        class L2TPRecipe(BaseRecipe):
            def test(self):
                m1 = self.matched.m1
                m1.l2tp = m1.init_class(L2TPManager)

                try:
                    self._test()
                finally:
                    m1.l2tp.cleanup()

            def _test(self):
                m1 = self.matched.m1

                m1.l2tp.create_tunnel(
                        tunnel_id=1000,
                        peer_tunnel_id=1000,
                        encap="udp",
                        local="192.168.200.1",
                        remote="192.168.200.2",
                        udp_sport=5000,
                        udp_dport=5000
                )
    """
    def __init__(self):
        self._tunnels = []

        try:
            self._l2tp_api = L2tp()
        except NetlinkError:
            raise L2tpConfigurationError(
                "Could not initialize pyroute's L2TP API. Please check if l2tp_eth module is loaded."
            )

    @property
    def l2tp_api(self):
        """
        This is a handle for the pyroute2's netlink l2tp API.
        """
        return self._l2tp_api

    def create_tunnel(self, **kwargs):
        """
        This method creates an L2TP tunnel based on the keyword arguments.
        These arguments should match the pyroute2's :meth:`L2tp.create_tunnel`
        arguments.
        """
        logging.info(f"Creating L2TP tunnel: {kwargs}")
        tunnel_id = kwargs["tunnel_id"]
        if tunnel_id in self._tunnels:
            raise L2tpConfigurationError(f"Tunnel with id {tunnel_id} already exists")

        response = self.l2tp_api.create_tunnel(**kwargs)
        if self._response_errors(response) is not None:
            raise L2tpConfigurationError(
                "Could not create L2TP tunnel {tunnel_id} through pyroute API"
            )

        self._tunnels.append(tunnel_id)
        return tunnel_id

    def cleanup(self):
        """
        This method deletes all tunnels created previously through the instance
        of this object. The method serves as a convenient way to cleanup at the
        end of a recipe.
        """
        for tunnel_id in self._tunnels:
            self.delete_tunnel(tunnel_id)

        self._tunnels.clear()

    def delete_tunnel(self, tunnel_id):
        """
        This method deletes the tunnel with the specified tunnel_id.
        """
        logging.info(f"Deleting L2TP tunnel: {tunnel_id}")
        response = self.l2tp_api.delete_tunnel(tunnel_id)
        if self._response_errors(response) is not None:
            raise L2tpDeconfigurationError(
                f"Could not delete L2TP tunnel {tunnel_id} through pyroute API"
            )

        return True

    def _response_errors(self, response):
        """
        delete response: ({'header': {'length': 36, 'type': 2, 'flags': 256, 'sequence_number': 258, 'pid': 4586, 'error': None, 'target': 'localhost', 'stats': Stats(qsize=0, delta=0, delay=0)}, 'event': 'NLMSG_ERROR'},)
        create response: ({'header': {'length': 36, 'type': 2, 'flags': 256, 'sequence_number': 255, 'pid': 4586, 'error': None, 'target': 'localhost', 'stats': Stats(qsize=0, delta=0, delay=0)}, 'event': 'NLMSG_ERROR'},)
        """
        for item in response:
            if item["event"] == "NLMSG_ERROR" and item["header"]["error"] is not None:
                return item["header"]["error"]

        return None
