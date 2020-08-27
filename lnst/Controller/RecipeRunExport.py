import datetime
import pickle
import os
import logging
from typing import List, Tuple
from lnst.Controller.Recipe import BaseRecipe, RecipeRun


class RecipeRunData:
    """
    Class used to encapsulate a RecipeRun, this is the object
    that will be pickled and output to a file.

    :param recipe_cls:
        class of the Recipe. We do not currently pickle the instance
        of the recipe itself for ease of exporting.
    :type recipe_cls: :py:class: `lnst.Controller.Recipe.BaseRecipe`

    :param param: Copy of Recipe parameters.
    :type param: dict

    :param req: Copy of Recipe requirements
    :type req: dict

    :param environ: A copy of `os.environ` created when the object is instantiated.
    :type environ: dict

    :param run: :py:class:`lnst.Controller.Recipe.RecipeRun` instance of the run
    :type run: :py:class:`lnst.Controller.Recipe.RecipeRun`

    :param datetime: A time stamp that is the result of running `datetime.datetime.now()` during instantiation
    :type datetime: :py:class:`datetime.datetime`
    """

    def __init__(self, recipe: BaseRecipe, run: RecipeRun):
        self.recipe_cls = recipe.__class__
        self.params = recipe.params._to_dict()
        self.req = recipe.req._to_dict()
        self.environ = os.environ.copy()
        self.run = run
        self.datetime = datetime.datetime.now()


class RecipeRunExporter:
    """
    Class used to export recipe runs.

    """

    def __init__(self, recipe: BaseRecipe):
        """

        :param recipe: Recipe
        :type recipe: :py:class: `lnst.Controller.Recipe.BaseRecipe`
        """
        self.recipe = recipe
        self.recipe_name = self.recipe.__class__.__name__

    def export_run(self, run: RecipeRun, dir=None, name=None) -> str:
        """

        :param run: The RecipeRun to export
        :type run: :py:class:`lnst.Controller.Recipe.RecipeRun`
        :param dir: The path to directory to export to. Does not include file name, defaults to `run.log_dir`
        :type dir: str
        :param name: Name of file to export. Default `<recipename>-run-<timestamp>.dat'
        :type name: str
        :return: Path (dir+filename) of exported run.
        :rtype:str
        """
        data = RecipeRunData(self.recipe, run)
        if not name:
            name = f"{self.recipe_name}-run-{data.datetime:%Y-%m-%d_%H:%M:%S}.dat"
        if not dir:
            dir = run.log_dir

        path = os.path.join(dir, name)

        with open(path, 'wb') as f:
            pickle.dump(data, f)

        logging.info(f"Exported {self.recipe_name} data to {path}")
        return path


def export_recipe_runs(recipe: BaseRecipe) -> List[Tuple[str, RecipeRun]]:
    """
    Helper method that exports all runs in a recipe.
    :param recipe: Recipe to export
    :type recipe: :py:class: `lnst.Controller.Recipe.BaseRecipe`
    :return: list of files that contain exported recipe runs
    :rtype: list
    """
    exporter = RecipeRunExporter(recipe)
    files = []
    for run in recipe.runs:
        path = exporter.export_run(run)
        files.append((run, path))
    return files


def import_recipe_run(path: str) -> RecipeRunData:
    """
    Import recipe runs that have been exported using :py:class:`lnst.Controller.RecipeRunExport.RecipeRunExporter`
    :param path:  path to file  to import
    :type path: str
    :return: `RecipeRun` object containing the run and other metadata.
    :rtype: :py:class:`lnst.Controller.RecipeRunExport.RecipeRunData`
    """
    with open(path, 'rb') as f:
        data = pickle.load(f)
    return data
