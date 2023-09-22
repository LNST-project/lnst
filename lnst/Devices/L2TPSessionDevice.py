"""
Defines the L2TPSessionDevice class.

Copyright 2021 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jtluka@redhat.com (Jan Tluka)
"""

from lnst.Common.DeviceError import DeviceError, DeviceConfigError
from lnst.Devices.Device import Device


class L2TPSessionDevice(Device):
    """
    This device class allows user to create L2TP sessions for tunnels
    previously created using the :any:`L2TPManager`.

    .. code-block:: python

        from lnst.Controller import BaseRecipe
        from lnst.Controller.Requirements import HostReq
        from lnst.RecipeCommon.L2TPManager import L2TPManager
        from lnst.Devices import L2TPSessionDevice

        class L2TPRecipe(BaseRecipe):
            m1 = HostReq()

            def test(self):
                m1 = self.matched.m1
                m1.l2tp = m1.init_class(L2TPManager)
                m1.l2tp.create_tunnel(
                        tunnel_id=1000,
                        peer_tunnel_id=1000,
                        encap="udp",
                        local="192.168.200.1",
                        remote="192.168.200.2",
                        udp_sport=5000,
                        udp_dport=5000

                m1.session1 = L2TPSessionDevice(
                        tunnel_id=1000,
                        session_id=2000,
                        peer_session_id=2000
                )
                m1.session1.up()
    """
    _name_template = "t_l2tp"
    #: mandatory options for the device
    _mandatory_opts = ["tunnel_id", "session_id", "peer_session_id"]

    def __init__(self, ifmanager, *args, **kwargs):
        from pyroute2.netlink import NetlinkError
        from pyroute2.netlink.generic.l2tp import L2tp
        global NetlinkError
        global L2tp

        self._name = None
        for i in self._mandatory_opts:
            if i not in kwargs:
                raise DeviceConfigError(
                    "Option {} is mandatory for type {}".format(
                        i, self.__class__.__name__
                    )
                )

        self._tunnel_id = tunnel_id = kwargs["tunnel_id"]
        self._session_id = kwargs["session_id"]
        self._peer_session_id = kwargs["peer_session_id"]
        self._ifmanager = ifmanager

        super(L2TPSessionDevice, self).__init__(ifmanager)

    def _create(self):
        try:
            self._l2tp_api = L2tp()
        except NetlinkError:
            raise DeviceError(
                "Could not initialize pyroute's L2TP API. Please check if l2tp_eth module is loaded."
            )

        session = {
            "tunnel_id": self._tunnel_id,
            "session_id": self._session_id,
            "peer_session_id": self._peer_session_id,
        }
        if self._name is None:
            self._name = session["ifname"] = self._ifmanager.assign_name(
                self._name_template
            )

        try:
            self._l2tp_api.create_session(**session)
        except NetlinkError as e:
            raise DeviceError(f"Could not create an L2TP session: {e}")

    def destroy(self):
        self._l2tp_api.delete_session(self._tunnel_id, self._session_id)
        return True

    @Device.name.getter
    def name(self):
        try:
            return super(L2TPSessionDevice, self).name
        except:
            return self._name

    @property
    def session_id(self):
        return self._session_id

    @property
    def peer_session_id(self):
        return self._peer_session_id

    @property
    def tunnel_id(self):
        return self._tunnel_id
