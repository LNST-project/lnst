import os
import sys
import traceback
from typing import Any, Type, Optional

from lnst.Recipes.ENRT import *
from lnst.Controller.Recipe import BaseRecipe
from lnst.Controller.Controller import Controller
from lnst.Controller.RecipeResults import ResultLevel, ResultType
from lnst.Controller.MachineMapper import ContainerMapper
from lnst.Controller.ContainerPoolManager import ContainerPoolManager

from lnst.Controller.RunSummaryFormatters import *
from lnst.Controller.RunSummaryFormatters.RunSummaryFormatter import RunSummaryFormatter


class ContainerRunner:
    """This class is responsible for running the LNST controller in a container.

    Environment variables:

    * DEBUG: Set to 1 to enable debug mode
    * RECIPE: Name of the recipe class to run
    * RECIPE_PARAMS: Parameters to pass to the recipe class
    * FORMATTERS: List of formatters to use
    * MULTIMATCH: Set to 1 to enable multimatch mode

    Agents in containers-specific environment variables:

    * PODMAN_URI: URI of the Podman socket
    * IMAGE_NAME: Name of the container image
    """

    def __init__(self) -> None:
        self._controller = Controller(**self._parse_controller_params())
        self._recipe_params: dict[str, Any] = self._parse_recipe_params()

        if not os.getenv("RECIPE"):
            raise ValueError("RECIPE environment variable is not set")
        self._recipe_cls: Type[BaseRecipe] = eval(os.getenv("RECIPE", ""))
        self._recipe: Optional[BaseRecipe] = None

        self._formatters: list[Type[RunSummaryFormatter]] = self._parse_formatters()

    def _parse_controller_params(self) -> dict:
        params = {
            "debug": bool(os.getenv("DEBUG", 0)),
        }

        if "PODMAN_URI" in os.environ:
            return params | {
                "podman_uri": os.getenv("PODMAN_URI"),
                "image": os.getenv("IMAGE_NAME", "lnst"),
                "network_plugin": "cni",
                "poolMgr": ContainerPoolManager,
                "mapper": ContainerMapper,
            }

        return params

    def _parse_recipe_params(self) -> dict[str, Any]:
        params = {}
        for param in os.getenv("RECIPE_PARAMS", "").split(";"):
            if not param:
                continue
            key, value = param.split("=")
            params[key] = eval(value)

        return params

    def _parse_formatters(self) -> list[Type[RunSummaryFormatter]]:
        return [
            eval(formatter)
            for formatter in os.getenv("FORMATTERS", "").split(";")
            if formatter
        ]

    def run(self) -> ResultType:
        """Initialize recipe class with parameters provided in `RECIPE_PARAMS`
        and execute. Function returns overall result.
        """
        overall_result = ResultType.PASS

        try:
            self._recipe = self._recipe_cls(**self._recipe_params)
            self._controller.run(
                self._recipe, multimatch=bool(os.getenv("MULTIMATCH", False))
            )
        except Exception:
            print("LNST Controller crashed with an exception:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            exit(ResultType.FAIL)

        for formatter in self._formatters:
            fmt = formatter(level=ResultLevel.IMPORTANT)
            for run in self._recipe.runs:
                print(fmt.format_run(run))
                overall_result = ResultType.max_severity(
                    overall_result, run.overall_result
                )

        return overall_result


if __name__ == "__main__":
    runner = ContainerRunner()
    exit_code = 0 if runner.run() == ResultType.PASS else 1
    exit(exit_code)
