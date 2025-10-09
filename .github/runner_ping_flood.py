import logging

from lnst.Controller import Controller
from lnst.Controller.ContainerPoolManager import ContainerPoolManager
from lnst.Controller.MachineMapper import ContainerMapper
from lnst.Controller.RunSummaryFormatters import HumanReadableRunSummaryFormatter
from lnst.Controller.RecipeResults import ResultLevel

from lnst.Recipes.ENRT import PingFloodRecipe

podman_uri = "unix:///run/podman/podman.sock"
image_name = "lnst"

try:
    recipe_instance = PingFloodRecipe()

    print("-----------------------------PingFlood START---------------------------")
    ctl = Controller(
        poolMgr=ContainerPoolManager,
        mapper=ContainerMapper,
        podman_uri=podman_uri,
        image=image_name,
        debug=1,
        network_plugin="custom_lnst"
    )

    ctl.run(recipe_instance)

    summary_fmt = HumanReadableRunSummaryFormatter(
        level=ResultLevel.IMPORTANT + 0, colourize=True
    )
    for run in recipe_instance.runs:
        logging.info(summary_fmt.format_run(run))
except Exception as e:
    logging.exception("Recipe PingFlood crashed with exception.")
    exit(1)

exit(0)
