import logging
import requests

from lnst.Recipes.ENRT.BaseLACPRecipe import BaseLACPRecipe
from lnst.Recipes.ENRT.ConfigMixins.BaseRESTConfigMixin import BaseRESTConfigMixin


class DellLACPRecipe(BaseRESTConfigMixin, BaseLACPRecipe):
    def __init__(self, *args, **kwargs):
        self._vlan_connections = {}  # structure: {"INTERFACE1": ["vlan10", "vlan20", ...]}

        super().__init__(*args, **kwargs)

    def get_interface_vlans(self, interfaces: list[str]):
        vlans = {interface: [] for interface in interfaces}

        infs = self.api_request(
            "get", "/restconf/data/ietf-interfaces:interfaces/interface"
        ).json()

        for sw_inf in infs["ietf-interfaces:interface"]:
            if (
                sw_inf["type"].lower() != "iana-if-type:l2vlan"
                or sw_inf["name"].lower() == "vlan1"
            ):
                # ^^ vlan1 is default vlan. Each inf is connected to it, this cannot be changed.
                continue

            for interface in interfaces:
                if interface in sw_inf["dell-interface:tagged-ports"]:
                    vlans[interface].append(sw_inf["name"])

        return vlans

    def test_wide_switch_configuration(self):
        self._vlan_connections = self.get_interface_vlans([interface for interfaces in self.params.topology.values() for interface in interfaces])

        logging.info(f"Interface/VLAN connections: {self._vlan_connections}")

        for bond, interfaces in self.params.topology.items():
            interfaces = [
                {"name": interface, "lacp-mode": self.params.lacp_mode}
                for interface in interfaces
            ]

            self.api_request(
                "patch",
                f"/restconf/data/ietf-interfaces:interfaces/interface/{bond}",
                response_code=204,
                json={
                    "ietf-interfaces:interface": [
                        {"name": bond, "dell-interface:member-ports": interfaces}
                    ]
                },
            )

    def test_wide_switch_deconfiguration(self):
        for bond, interfaces in self.params.topology.items():
            for interface in interfaces:
                self.api_request(
                    "delete",
                    f"/restconf/data/ietf-interfaces:interfaces/interface/{bond}",
                    response_code=204,
                    json={"dell-interface:member-ports": [{"name": interface}]},
                )

        for interface, vlans in self._vlan_connections.items():
            self.api_request(
                "put",
                f"/restconf/data/ietf-interfaces:interfaces/interface/{requests.utils.quote(interface, safe='')}/dell-interface{requests.utils.quote(':')}mode",
                response_code=204,
                json={"dell-interface:mode": "MODE_L2HYBRID"},
            )
            logging.info(f"Interface {interface} set to MODE_L2HYBRID")

            for vlan in vlans:
                self.api_request(
                    "put",
                    f"/restconf/data/ietf-interfaces:interfaces/interface/{vlan}/dell-interface{requests.utils.quote(':')}tagged-ports",
                    response_code=204,
                    json={"dell-interface:tagged-ports": [interface]},
                )
                logging.info(f"Vlan {vlan} added to interface {interface}")

