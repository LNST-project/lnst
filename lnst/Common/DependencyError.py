import logging

from lnst.Common.LnstError import LnstError


class DependencyError(LnstError):
    def __init__(self, module: ModuleNotFoundError):
        self._module = module.name

        self._msg = f"Could not import {self._module}, please install it."

        logging.error(self._msg)

    def __str__(self):
        return self._msg
