import inspect

from lnst.Controller import Controller
from lnst.Controller.ContainerPoolManager import ContainerPoolManager
from lnst.Controller.MachineMapper import ContainerMapper
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe

import lnst.Recipes.ENRT as enrt_recipes

podman_uri = "unix:///run/podman/podman.sock"
image_name = "lnst"
ctl = Controller(
    poolMgr=ContainerPoolManager,
    mapper=ContainerMapper,
    podman_uri=podman_uri,
    image=image_name,
    debug=1,
)

params = dict(
    perf_tests=['tcp_stream'],
    perf_duration=5,
    perf_iterations=2,
    perf_warmup_duration=0,
    ping_count=1,
    perf_test_simulation=True,
)

for recipe_name in dir(enrt_recipes):
    if recipe_name in ["BaseEnrtRecipe", "BaseTunnelRecipe", "BaseLACPRecipe"]:
        continue

    recipe = getattr(enrt_recipes, recipe_name)

    if not (inspect.isclass(recipe) and issubclass(recipe, BaseEnrtRecipe)):
        continue

    if "Bond" in recipe_name:
        params = params.copy()
        params["bonding_mode"] = "active-backup"
        params["miimon_value"] = 5

    recipe_instance = recipe(**params)

    ctl.run(recipe_instance)

    overall_result = all([run.overall_result for run in recipe_instance.runs])

