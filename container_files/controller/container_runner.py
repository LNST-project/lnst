import json
import os
import sys
import traceback
import zipfile
from functools import reduce
from typing import Any, Type

from lnst.Recipes.ENRT import *
from lnst.Controller.Recipe import BaseRecipe, export_recipe_run
from lnst.Controller.Controller import Controller
from lnst.Controller.RecipeResults import ResultLevel, ResultType
from lnst.Controller.MachineMapper import ContainerMapper
from lnst.Controller.ContainerPoolManager import ContainerPoolManager

from lnst.Controller.RunSummaryFormatters import *
from lnst.Controller.RunSummaryFormatters.RunSummaryFormatter import RunSummaryFormatter

from container_files.controller.test_db import tests as test_db_tests

RESULTS_DIR = "/root/.lnst/results"
POOL_DIR = "/root/.lnst/pool"


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

    def _export_results(self, recipe, result_dir):
        os.makedirs(result_dir, exist_ok=True)

        # Export human-readable log (with debug output)
        hr_fmt = HumanReadableRunSummaryFormatter(level=ResultLevel.DEBUG)
        with open(os.path.join(result_dir, "controller.log"), "w") as f:
            for run in recipe.runs:
                f.write(hr_fmt.format_run(run))
                f.write("\n")

        # Export JSON results and LRC files per run
        json_fmt = JsonRunSummaryFormatter(pretty=True)
        for i, run in enumerate(recipe.runs):
            # LRC export
            lrc_filename = f"run-data-{i}.lrc"
            try:
                export_recipe_run(run, export_dir=result_dir, name=lrc_filename)
            except Exception:
                print(f"Failed to export {lrc_filename}:", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)

            # JSON export
            json_filename = f"run-data-{i}.json"
            with open(os.path.join(result_dir, json_filename), "w") as f:
                try:
                    f.write(json_fmt.format_run(run))
                except Exception as exc:
                    exception_result = {
                        "result": "FAIL",
                        "type": "exception",
                        "message": str(exc),
                    }
                    json.dump([exception_result], f, indent=4)

    def _zip_results(self):
        zip_path = os.path.join(RESULTS_DIR, "results.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(RESULTS_DIR):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    if fpath == zip_path:
                        continue
                    arcname = os.path.relpath(fpath, RESULTS_DIR)
                    zf.write(fpath, arcname)

    def run(self) -> ResultType:
        """Execute all tests from test_db sequentially.

        Each test is independent -- a failure in one test does not prevent
        subsequent tests from running.  A summary is printed at the end.
        """
        overall = ResultType.PASS
        results: list[tuple[str, ResultType]] = []

        for i, test in enumerate(self._test_db):
            print(f"\n{'=' * 60}")
            recipe_name = test["recipe_name"]

            test_result = ResultType.PASS
            recipe = None
            try:
                recipe_cls = eval(recipe_name)
                recipe = recipe_cls(**test.get("params", {}))
                self._controller.run(
                    recipe, multimatch=bool(os.getenv("MULTIMATCH", False))
                )

                test_result = reduce(
                    ResultType.max_severity,
                    (run.overall_result for run in recipe.runs),
                    ResultType.PASS,
                )
            except Exception:
                print(
                    f"Test {recipe_name} crashed with an exception:",
                    file=sys.stderr,
                )
                traceback.print_exc(file=sys.stderr)
                test_result = ResultType.FAIL

            if recipe is not None:
                try:
                    result_dir = f"{RESULTS_DIR}/{i}_{recipe_name}"
                    self._export_results(recipe, result_dir)
                except Exception:
                    print(
                        f"Failed to export results for {recipe_name}:",
                        file=sys.stderr,
                    )
                    traceback.print_exc(file=sys.stderr)

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


def _check_dir_access(path):
    """Check if a directory exists and is accessible, warn about SELinux if not."""
    if os.path.isdir(path):
        try:
            os.listdir(path)
        except PermissionError:
            print(
                f"Permission denied accessing {path}. "
                "If this directory is a mounted volume, SELinux may be "
                "preventing access. Try running the container with "
                "--security-opt label=disable",
                file=sys.stderr,
            )
            sys.exit(1)


if __name__ == "__main__":
    _check_dir_access(POOL_DIR)
    _check_dir_access(RESULTS_DIR)
    runner = ContainerRunner()
    exit_code = 0 if runner.run() == ResultType.PASS else 1
    runner._zip_results()
    exit(exit_code)
