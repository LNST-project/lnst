import os
import sys
import traceback
from typing import Any, Type

from lnst.Recipes.ENRT import *
from lnst.Controller.Recipe import BaseRecipe
from lnst.Controller.Controller import Controller
from lnst.Controller.RecipeResults import ResultLevel, ResultType
from lnst.Controller.MachineMapper import ContainerMapper
from lnst.Controller.ContainerPoolManager import ContainerPoolManager

from lnst.Controller.RunSummaryFormatters import *
from lnst.Controller.RunSummaryFormatters.RunSummaryFormatter import RunSummaryFormatter

from container_files.controller.test_db import tests as test_db_tests


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

        if os.getenv("RECIPE"):
            self._test_db = [
                {
                    "recipe_name": os.getenv("RECIPE", ""),
                    "params": self._parse_recipe_params(),
                },
            ]
        else:
            self._test_db = test_db_tests

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
        """Execute all tests from test_db sequentially.

        Each test is independent -- a failure in one test does not prevent
        subsequent tests from running.  A summary is printed at the end.
        """
        overall = ResultType.PASS
        results: list[tuple[str, ResultType]] = []

        for test in self._test_db:
            print(f"\n{'=' * 60}")
            recipe_name = test["recipe_name"]

            test_result = ResultType.PASS
            try:
                recipe_cls = eval(recipe_name)
                recipe = recipe_cls(**test.get("params", {}))
                self._controller.run(
                    recipe, multimatch=bool(os.getenv("MULTIMATCH", False))
                )
            except Exception:
                print(
                    f"Test {recipe_name} crashed with an exception:",
                    file=sys.stderr,
                )
                traceback.print_exc(file=sys.stderr)
                test_result = ResultType.FAIL

            results.append((recipe_name, test_result))
            overall = ResultType.max_severity(overall, test_result)

        print(f"\n{'=' * 60}")
        print("Test Summary:")
        print(f"{'=' * 60}")
        for i, (recipe_name, result) in enumerate(results):
            status = "PASS" if result == ResultType.PASS else "FAIL"
            print(f"  {i}_{recipe_name}: {status}")
        overall_status = "PASS" if overall == ResultType.PASS else "FAIL"
        print(f"\nOverall result: {overall_status}")

        return overall


if __name__ == "__main__":
    runner = ContainerRunner()
    exit_code = 0 if runner.run() == ResultType.PASS else 1
    exit(exit_code)
