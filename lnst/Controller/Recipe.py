"""
Module implementing the BaseRecipe class.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import copy
import datetime
import logging
import lzma
import os
import pickle
from lnst.Common.Parameters import Parameters, Param
from lnst.Common.Colours import decorate_with_preset
from lnst.Controller.Requirements import _Requirements, HostReq
from lnst.Controller.Common import ControllerError
from lnst.Controller.RecipeResults import BaseResult, Result

class RecipeError(ControllerError):
    """Exception thrown by the BaseRecipe class"""
    pass

class BaseRecipe(object):
    """Base class for LNST Recipe definition.

    Every LNST Recipe written by testers should be inherited from this class.
    An LNST Recipe is composed of several parts:

    * Requirements definition - you define recipe requirements in a derived
      class by defining class attributes of the HostReq type. You can further
      specify Ethernet Device requirements by defining DeviceReq attributes of
      the :py:class:`lnst.Controller.Requirements.HostReq` object. Example::

        class MyRecipe(BaseRecipe):
            m1 = HostReq(arch="x86_64")
            m1.eth0 = DeviceReq(driver="ixgbe")

    * Parameter definition (optional) - you can define paramaters of your
      Recipe by defining class attributes of the :any:`Param` type (or
      inherited).  These parameters can then be accessed from the test() method
      to change it's behaviour. Parameter validity (type) is checked during the
      instantiation of the Recipe object by the base __init__ method.  You can
      define your own __init__ method to implement more complex Parameter
      checking if needed, but you MUST call the base __init__ method first.
      Example::

        class MyRecipe(BaseRecipe):
            int_param = IntParam(mandatory=True)
            optional_param = IntParam()

            def test(self):
                x = self.params.int_param
                if "optional_param" in self.params:
                    x += self.params.optional_param

        MyRecipe(int_param = 2, optional_param = 3)

    * Test definition - this is done by defining the test() method, in this
      method the tester has direct access to mapped LNST agent Hosts, can
      manipulate them and implement his tests.

    :ivar matched:
        When running the Recipe the Controller will fill this attribute with a
        Hosts object after the Mapper finds suitable agent hosts.
    :type matched: :py:class:`lnst.Controller.Host.Hosts`

    :ivar req:
        Instantiated Requirements object, you can optionally change the Recipe
        requirements through this object during runtime (e.g.  variable number
        of hosts or devices of a host based on a Parameter)
    :type req: :py:class:`lnst.Controller.Requirements._Requirements`

    :ivar params:
        Instantiated Parameters object, can be used to access the calculated
        parameters during Recipe initialization/execution
    :type params: :py:class:`lnst.Common.Parameters.Parameters`
    """
    def __init__(self, **kwargs):
        """
        The __init__ method does 2 things:
        * copies Requirements -- since Requirements are defined as class
            attributes, we need to copy the objects to avoid conflicts with
            multiple instances of the same class etc...
            The copied objects are stored under a Requirements object available
            through the 'req' attribute. This way you can optionally change the
            Requirements of an instantiated Recipe.
        * copies and instantiates Parameters -- Parameters are also class
            attributes so they need to be copied into a Parameters() object
            (accessible in the 'params' attribute).
            Next, the copied objects are loaded with values from kwargs
            and checked if mandatory Parameters have values.
        """
        self._ctl = None
        self.runs = []
        self.req = _Requirements()
        self.params = Parameters()

        attrs = {name: getattr(type(self), name) for name in dir(type(self))}

        params = ((name, val) for name, val in attrs.items() if isinstance(val, Param))
        for name, val in params:
            if name in kwargs:
                param_val = kwargs.pop(name)
                param_val = val.type_check(param_val)
                setattr(self.params, name, param_val)
            else:
                try:
                    param_val = copy.deepcopy(val.default)
                    setattr(self.params, name, param_val)
                except AttributeError:
                    if val.mandatory:
                        raise RecipeError("Parameter {} is mandatory".format(name))

        reqs = ((name, val) for name, val in attrs.items() if isinstance(val, HostReq))
        for name, val in reqs:
            new_val = copy.deepcopy(val)
            new_val.reinit_with_params(self.params)
            setattr(self.req, name, new_val)

        if len(kwargs):
            for key in list(kwargs.keys()):
                raise RecipeError("Unknown parameter {}".format(key))

    @property
    def ctl(self):
        return self._ctl

    def _set_ctl(self, ctl):
        self._ctl = ctl


    @property
    def matched(self):
        if self.ctl is None:
            return None
        return self.ctl.hosts

    def test(self):
        """Method to be implemented by the Tester"""
        raise NotImplementedError("Method test must be defined by a child class.")

    def _init_run(self, run):
        self.runs.append(run)

    @property
    def current_run(self):
        if len(self.runs) > 0:
            return self.runs[-1]
        else:
            return None

    def add_result(self, success, description="", data=None,
                   level=None, data_level=None):
        self.current_run.add_result(Result(success, description, data,
                                           level, data_level))

    def __getstate__(self):
        state = self.__dict__.copy()
        state['_ctl'] = None
        return state


class RecipeRun(object):
    def __init__(self, recipe: BaseRecipe, match, desc=None, log_dir=None, log_list=None):
        self._match = match
        self._desc = desc
        self._results = []
        self._log_dir = log_dir
        self._log_list = log_list
        self._recipe = recipe
        self._datetime = datetime.datetime.now()
        self._environ = os.environ.copy()
        self._exception = None

    def add_result(self, result):
        if not isinstance(result, BaseResult):
            raise RecipeError("result must be a BaseActionResult instance.")

        self._results.append(result)

        result_str = (
            decorate_with_preset("PASS", "pass")
            if result.success
            else decorate_with_preset("FAIL", "fail")
        )
        if len(result.description.split("\n")) == 1:
            logging.info(
                "Result: {}, What: {}".format(result_str, result.description)
            )
        else:
            logging.info("Result: {}, What:".format(result_str))
            logging.info("{}".format(result.description))

    @property
    def log_dir(self):
        return self._log_dir

    @property
    def log_list(self):
        return self._log_list

    @property
    def match(self):
        return self._match

    @property
    def description(self):
        return self._desc

    @property
    def results(self):
        return self._results

    @property
    def overall_result(self):
        return all([i.success for i in self.results] + [self.exception is None])

    @property
    def recipe(self) -> BaseRecipe:
        return self._recipe

    @property
    def datetime(self):
        return self._datetime

    @property
    def environ(self):
        return self._environ

    @property
    def exception(self):
        return self._exception

    @exception.setter
    def exception(self, exception):
        self._exception = exception

def export_recipe_run(run: RecipeRun, export_dir: str = None, name: str = None) -> str:
    """
    Export a recipe run to a file. :py:class:`RecipeRun` is pickled and compressed.

    :param run: `RecipeRun` object to export.
    :type run: :py:class:`RecipeRun`
    :param export_dir: Directory to export file to. Defaults to :py:attr:`run.log_dir`
    :type export_dir: str
    :param name: Name of output (exclusive of directory). Defaults to `<recipename>-run-<timestamp>.lrc`.
    :type name: str
    :return: Path of output file.
    :rtype: str

    Example::

        ctl = Controller(...)
        recipe = BondRecipe(...)
        ctl.run(recipe)
        ...
        >>> from lnst.Controller.Recipe import export_recipe_run
        >>> path = export_recipe_run(recipe.run[0])
        2020-10-02 15:20:58 (localhost) - INFO: Exported BondRecipe run data to /tmp/lnst-logs/2020-10-02_15:20:18/BondRecipe_match_0/BondRecipe-run-2020-10-02_15:20:58.lrc
        >>> print(path)
        /tmp/lnst-logs/2020-10-02_15:20:18/BondRecipe_match_0/BondRecipe-run-2020-10-02_15:20:58.lrc

    """
    if not name:
        name = f"{run.recipe.__class__.__name__}-run-{run.datetime:%Y-%m-%d_%H:%M:%S}.lrc"
    if not export_dir:
        export_dir = run.log_dir

    path = os.path.join(export_dir, name)
    with lzma.open(path, 'wb') as f:
        pickle.dump(run, f)
    logging.info(f"Exported {run.recipe.__class__.__name__} run to {path}")
    return path


def import_recipe_run(path: str) -> RecipeRun:
    """
    Import a recipe run that was exported using :py:meth:`export_recipe_run`

    :param path: Path to file to import
    :type path:  str
    :return: object which contains the imported recipe run
    :rtype:  :py:class:`RecipeRun`

    Example::

        >>> from lnst.Controller.Recipe import import_recipe_run
        >>> run = import_recipe_run("/tmp/lnst-logs/2020-10-02_15:20:18/BondRecipe_match_0/BondRecipe-run-2020-10-02_15:20:58.lrc")
        >>> type(run)
        <class 'lnst.Controller.Recipe.RecipeRun'>
        >>> run.recipe.__class__
        <class 'lnst.Recipes.ENRT.BondRecipe.BondRecipe'>
        >>> run.results[38]
        <lnst.Controller.RecipeResults.Result object at 0x7f20727e1e20>
        >>> run.results[38].data
        {'cpu': [[[<lnst.RecipeCommon.Perf.Results.PerfInterval object at 0x7f20727e1e50>,...]]], ... }
        >>> print(run.results[38].description)
        CPU Utilization on host host1:
        cpu 'cpu': 45.40 +-0.00 time units per second
        cpu 'cpu0': 45.40 +-0.00 time units per second
    """
    with lzma.open(path, 'rb') as f:
        run = pickle.load(f)
    return run
