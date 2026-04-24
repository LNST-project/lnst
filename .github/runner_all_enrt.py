import inspect
import logging
import subprocess
import sys
import os
from pathlib import Path

from lnst.Controller import Controller
from lnst.Controller.ContainerPoolManager import ContainerPoolManager
from lnst.Controller.MachineMapper import ContainerMapper
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from lnst.Recipes.ENRT.BondingMixin import BondingMixin
from lnst.Recipes.ENRT.BaseSRIOVNetnsTcRecipe import BaseSRIOVNetnsTcRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import OffloadSubConfigMixin

import lnst.Recipes.ENRT as enrt_recipes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)


def get_changed_files():
    """
    Get list of changed files in the PR or commit.
    Returns None if detection fails (will run all recipes - conservative approach).
    """
    try:
        # GitHub Actions environment variables
        base_ref = os.environ.get('GITHUB_BASE_REF')  # Set for pull_request events
        event_name = os.environ.get('GITHUB_EVENT_NAME', '')

        if base_ref and event_name == 'pull_request':
            # Pull request - compare against base branch
            # Use three-dot diff to compare merge-base with HEAD
            logging.info(f"Detected pull request, comparing with base branch: {base_ref}")
            result = subprocess.run(
                ['git', 'diff', '--name-only', f'origin/{base_ref}...HEAD'],
                capture_output=True,
                text=True,
                check=True
            )
        elif event_name == 'push':
            # Push to master - compare with previous commit
            logging.info("Detected push event, comparing with previous commit")
            result = subprocess.run(
                ['git', 'diff', '--name-only', 'HEAD^', 'HEAD'],
                capture_output=True,
                text=True,
                check=True
            )
        else:
            # Fallback: try to detect if we're in a PR or push
            # Check if HEAD^ exists (at least 2 commits)
            logging.info(f"fallback ... {base_ref} {event_name}")
            check_result = subprocess.run(
                ['git', 'rev-parse', '--verify', 'HEAD^'],
                capture_output=True,
                check=False
            )
            if check_result.returncode == 0:
                logging.info("Fallback: comparing with previous commit")
                result = subprocess.run(
                    ['git', 'diff', '--name-only', 'HEAD^', 'HEAD'],
                    capture_output=True,
                    text=True,
                    check=True
                )
            else:
                logging.warning("Could not determine comparison strategy. Running all recipes.")
                return None

        changed_files = [f.strip() for f in result.stdout.split('\n') if f.strip()]

        if not changed_files:
            logging.info("No changed files detected")

        return changed_files
    except Exception as e:
        logging.warning(f"Could not detect changed files: {e}. Running all recipes.")
        return None


def get_recipe_module_path(recipe_class):
    """Get the file path of a recipe class relative to repository root."""
    try:
        module = inspect.getmodule(recipe_class)
        if module and hasattr(module, '__file__'):
            # Convert absolute path to relative path from repo root
            abs_path = Path(module.__file__).resolve()
            repo_root = Path(__file__).resolve().parent.parent
            return str(abs_path.relative_to(repo_root))
    except Exception:
        pass
    return None


def get_recipe_dependencies(recipe_class):
    """
    Get all classes that this recipe depends on (base classes and mixins).
    Returns their module paths.
    """
    dependencies = set()

    # Get all base classes (MRO - Method Resolution Order)
    for base in inspect.getmro(recipe_class):
        if base == object:
            continue
        dep_path = get_recipe_module_path(base)
        if dep_path:
            dependencies.add(dep_path)

    return dependencies


def should_run_recipe(recipe_class, changed_files):
    """
    Determine if a recipe should be run based on changed files.

    Returns True if:
    - changed_files is None (couldn't detect changes, run all)
    - The recipe's own file was changed
    - Any of the recipe's dependencies (base classes, mixins) were changed
    - Core infrastructure was changed (conservative approach)
    """
    if changed_files is None:
        return True

    # Check if any core infrastructure changed (run all tests)
    core_paths = [
        'lnst/Controller/',
        'lnst/Common/',
        'lnst/RecipeCommon/',
        'lnst/Devices/',
        'lnst/Tests/',
    ]

    for changed_file in changed_files:
        for core_path in core_paths:
            if changed_file.startswith(core_path):
                logging.info(f"Core infrastructure changed ({changed_file}), running all recipes")
                return True

    # Get all files this recipe depends on
    recipe_deps = get_recipe_dependencies(recipe_class)

    # Check if any of the recipe's dependencies were changed
    for changed_file in changed_files:
        if changed_file in recipe_deps:
            return True

    return False


podman_uri = "unix:///run/podman/podman.sock"
image_name = "lnst"

params_base = dict(
    perf_tests=['tcp_stream'],
    perf_duration=5,
    perf_iterations=2,
    perf_warmup_duration=0,
    ping_count=1,
    perf_test_simulation=True,
)

# Check if we should run all recipes regardless of changes
run_all = '--all' in sys.argv or '--force-all' in sys.argv

# Detect changed files to determine which recipes to run
if run_all:
    logging.info("Running all recipes (--all flag specified)")
    changed_files = None
else:
    changed_files = get_changed_files()
    if changed_files:
        logging.info(f"Detected {len(changed_files)} changed files")
        for f in changed_files:
            logging.info(f"  - {f}")
    else:
        logging.info("Running all recipes (could not detect changes)")

i = 0
recipe_results = {}
skipped_recipes = []

for recipe_name in dir(enrt_recipes):
    if recipe_name in ["BaseEnrtRecipe", "BaseTunnelRecipe", "BaseLACPRecipe", "DellLACPRecipe", "BaseSRIOVNetnsTcRecipe"]:
        continue
    elif "Ovs" in recipe_name or "OvS" in recipe_name:
        # ovs can't run without systemd service so containers don't work correctly
        continue
    elif recipe_name == "SimpleNetworkTunableRecipe":
        # veth doesn't support hash functions
        continue
    elif "Team" in recipe_name:
        # teaming has some unexplained issues right now
        # TODO check?
        continue
    elif recipe_name in ["L2TPTunnelRecipe"]:
        continue
    elif recipe_name in ["ForwardingRecipe", "XDPForwardingRecipe"]:
        # forwarding recipes requires 2 hosts with 2 NICs each
        # XDPForwarding requires 2 physical NICs on forwarding host
        continue

    recipe = getattr(enrt_recipes, recipe_name)

    if not (inspect.isclass(recipe) and issubclass(recipe, BaseEnrtRecipe)):
        continue
    elif issubclass(recipe, BaseSRIOVNetnsTcRecipe):
        # veth doesn't support sriov
        continue

    # Check if this recipe should run based on changed files
    if not should_run_recipe(recipe, changed_files):
        logging.info(f"Skipping {recipe_name} (not impacted by changes)")
        skipped_recipes.append(recipe_name)
        continue

    i += 1

    params = params_base.copy()

    if issubclass(recipe, BondingMixin) or recipe_name in[ "GreTunnelOverBondRecipe", "LinuxBridgeOverBondRecipe", "TeamVsBondRecipe", "VirtualBridgeVlansOverBondRecipe", "VlansOverBondRecipe"]:
        params["bonding_mode"] = "active-backup"
        params["miimon_value"] = 5
    elif issubclass(recipe, enrt_recipes.TeamRecipe) or issubclass(recipe, enrt_recipes.DoubleTeamRecipe):
        params["runner_name"] = "activebackup"
    elif recipe_name.startswith("CT"):
        del params["perf_tests"]
        if "CTFulltableInsertionRateRecipe" in recipe_name:
            params["long_lived_conns"] = 10000
    elif recipe_name == "SoftwareRDMARecipe":
        del params["perf_tests"]
    elif recipe_name == "ShortLivedConnectionsRecipe":
        del params["perf_tests"]

    if recipe_name in ["GeneveLwtTunnelRecipe", "GreLwtTunnelRecipe", "L2TPTunnelRecipe", "VxlanLwtTunnelRecipe", "GeneveTunnelRecipe", "VxlanGpeTunnelRecipe"]:
        params["carrier_ipversion"] = "ipv4"

    if recipe_name in ["SitTunnelRecipe", "IpIpTunnelRecipe"]:
        params["tunnel_mode"] = "any"
    if recipe_name in ["Ip6TnlTunnelRecipe"]:
        params["tunnel_mode"] = "ip6ip6"

    if recipe_name == "SoftwareRDMARecipe":
        params["software_rdma_type"] = "rxe"

    if recipe_name in ["XDPDropRecipe", "XDPTxRecipe"]:
        params["multi_dev_interrupt_config"] = {
            "host1": {"eth0": {"cpus": [0], "cpu_policy": "round-robin"}},
            "host2": {"eth0": {"cpus": [0], "cpu_policy": "round-robin"}},
        }
        params["perf_tool_cpu"] = [0]

    if recipe_name == "NftablesRuleScaleRecipe":
        params["rule"] = "accept"
        params["scale"] = 1

    if issubclass(recipe, OffloadSubConfigMixin):
        params['offload_combinations'] = []

    try:
        recipe_instance = recipe(**params)

        print(f"-----------------------------{recipe_name} {i}START---------------------------")
        ctl = Controller(
            poolMgr=ContainerPoolManager,
            mapper=ContainerMapper,
            podman_uri=podman_uri,
            image=image_name,
            debug=1,
            network_plugin="custom_lnst"
        )
        ctl.run(recipe_instance)

        overall_result = all([run.overall_result for run in recipe_instance.runs])
        recipe_results[recipe_name] = "PASS" if overall_result else "FAIL"
    except Exception as e:
        logging.exception(f"Recipe {recipe_name} crashed with exception.")
        recipe_results[recipe_name] = f"EXCEPTION: {e}"

print("\n" + "="*80)
print("SUMMARY")
print("="*80)

if skipped_recipes:
    print(f"\nSkipped {len(skipped_recipes)} recipes (not impacted by changes):")
    for recipe_name in sorted(skipped_recipes):
        print(f"  - {recipe_name}")

print(f"\nRan {len(recipe_results)} recipes:")
for recipe_name, result in recipe_results.items():
    print(f"  {recipe_name}: {result}")

print("="*80)

exit(any(result.startswith("EXCEPTION") for result in recipe_results.values()))
