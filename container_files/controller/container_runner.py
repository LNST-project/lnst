import json
import os
import shutil
import ssl
import sys
import traceback
import zipfile
from functools import reduce
from typing import Any
from urllib.request import urlopen

from lnst.Recipes.ENRT import *
from lnst.Controller.Recipe import BaseRecipe, export_recipe_run
from lnst.Controller.Controller import Controller
from lnst.Controller.RecipeResults import ResultLevel, ResultType
from lnst.Controller.MachineMapper import ContainerMapper
from lnst.Controller.ContainerPoolManager import ContainerPoolManager

from lnst.Controller.RunSummaryFormatters import *

RESULTS_DIR = "/root/.lnst/results"
POOL_DIR = "/root/.lnst/pool"
TEST_DB = os.getenv("TEST_DB", "/lnst/container_files/controller/test_db.json")


class ContainerRunner:
    """This class is responsible for running the LNST controller in a container.

    Environment variables:

    * DEBUG: Set to 1 to enable debug mode
    * RECIPE: Name of the recipe class to run
    * RECIPE_PARAMS: Parameters to pass to the recipe class
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
            self._test_db = self._load_test_db()


    @staticmethod
    def _load_test_db() -> list[dict[str, Any]]:
        uri = TEST_DB
        if "://" not in uri:
            uri = f"file://{uri}"

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with urlopen(uri, context=ctx) as resp:
            return json.load(resp)

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

    def _export_results(self, recipe, result_dir):
        log_dir = f"{result_dir}/logs"

        # Export human-readable result summary (with debug output)
        hr_fmt = HumanReadableRunSummaryFormatter(level=ResultLevel.DEBUG)
        try:
            with open(os.path.join(log_dir, "result_summary.log"), "w") as f:
                for run in recipe.runs:
                    f.write(hr_fmt.format_run(run))
                    f.write("\n")
        except Exception:
            print("Failed to export result_summary.log:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

        # Export per-host log files from log_dir
        for run in recipe.runs:
            if not run.log_dir or not os.path.isdir(run.log_dir):
                continue
            try:
                shutil.copytree(run.log_dir, log_dir, dirs_exist_ok=True)
            except Exception:
                print("Failed to copy log_dir:", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)

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
        overall_result = ResultType.PASS
        results: list[tuple[str, ResultType]] = []

        for i, test in enumerate(self._test_db):
            print(f"\n{'=' * 60}")
            recipe_name = test["recipe_name"]
            test_id = test.get("uuid", f"{i}_{recipe_name}")

            recipe = None
            exc_info = None
            result_dir = f"{RESULTS_DIR}/{test_id}"
            log_dir = f"{result_dir}/logs"
            os.makedirs(log_dir, exist_ok=True)
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
                exc_info = traceback.format_exc()

            if recipe is not None:
                try:
                    self._export_results(recipe, result_dir)
                except Exception:
                    print(
                        f"Failed to export results for {recipe_name}:",
                        file=sys.stderr,
                    )
                    traceback.print_exc(file=sys.stderr)

            if exc_info is not None:
                with open(os.path.join(log_dir, "crash.log"), "w") as f:
                    f.write(exc_info)

            results.append((test_id, test_result))
            overall_result = ResultType.max_severity(overall_result, test_result)

        print(f"\n{'=' * 60}")
        print("Test Summary:")
        print(f"{'=' * 60}")
        for test_id, result in results:
            status = "PASS" if result == ResultType.PASS else "FAIL"
            print(f"  {test_id}: {status}")
        print(f"\nOverall result: {'PASS' if overall_result == ResultType.PASS else 'FAIL'}")

        return overall_result


def _check_dir_access(path):
    """Check if a directory exists and is accessible, warn about SELinux if not."""
    if not os.path.isdir(path):
        print(f"Directory {path} does not exist or is not a directory.", file=sys.stderr)
        return False

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
        return False
    return True


if __name__ == "__main__":
    if not _check_dir_access(POOL_DIR) or not _check_dir_access(RESULTS_DIR):
        sys.exit(1)
    runner = ContainerRunner()
    try:
        exit_code = 0 if runner.run() == ResultType.PASS else 1
    except Exception:
        traceback.print_exc(file=sys.stderr)
        exit_code = 1
    finally:
        runner._zip_results()
    exit(exit_code)
