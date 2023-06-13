from lnst.Recipes.ENRT.BaseLACPRecipe import BaseLACPRecipe
from lnst.Recipes.ENRT.ConfigMixins.BaseRESTConfigMixin import BaseRESTConfigMixin


class DellLACPRecipe(BaseRESTConfigMixin, BaseLACPRecipe):
    def test_wide_switch_configuration(self):
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
                        {
                            "name": bond,
                            "dell-interface:member-ports": interfaces
                        }
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
                    json={
                        "dell-interface:member-ports": [{"name": interface}]
                    }
                )
