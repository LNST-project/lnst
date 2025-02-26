"""
This module defines the Controller class that brings together individual
implementation parts of an LNST Controller. When instantiated, it allows the
tester to configure and run his own recipes with the LNST 'infrastructure'.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import os
import sys
from typing import Union
import datetime
import logging
from lnst.Common.Logs import LoggingCtl, log_exc_traceback
from lnst.Common.NetUtils import MacPool
from lnst.Common.Utils import mkdir_p
from lnst.Devices.VirtualDevice import VirtualDevice
from lnst.Controller.Common import ControllerError
from lnst.Controller.Config import CtlConfig
from lnst.Controller.MessageDispatcher import MessageDispatcher
from lnst.Controller.AgentPoolManager import AgentPoolManager
from lnst.Controller.ContainerPoolManager import ContainerPoolManager
from lnst.Controller.MachineMapper import MachineMapper
from lnst.Controller.MachineMapper import format_match_description
from lnst.Controller.Host import Hosts, Host
from lnst.Controller.Recipe import BaseRecipe, RecipeRun
from lnst.Controller.RecipeControl import RecipeControl

class Controller(object):
    """Allows to run LNST Recipe instances

    This is the main mechanism that allows users to create their own executable
    test scripts that execute LNST Recipes.

    The Controller class implementation provides the most common default values
    for various parameters that can significantly change the way that Recipes
    are executed. This includes custom implementations of classes that are used
    for setting up the testing infrastructure such as the PoolManager or the
    MachineMapper.

    :param poolMgr:
        class that implements the
        :py:class:`lnst.Controller.AgentPoolManager.AgentPoolManager` interface
        will be instantiated by the Controller to provide the mapper with pools
        available for matching, also handles the creation of
        :py:class:`Machine` objects (internal LNST class used to access the
        agent hosts)
    :type poolMgr:
        :py:class:`lnst.Controller.AgentPoolManager.AgentPoolManager`
        (this is also the default class)

    :param mapper:
        class that implements the
        :py:class:`lnst.Controller.MachineMapper.MachineMapper` interface will
        be instantiated by the Controller to match Recipe requirements to the
        available pools
    :type mapper: :py:class:`lnst.Controller.MachineMapper.MachineMapper`
        (this is also the default class)

    :param config:
        optional LNST configuration object, if None the Controller will
        load it's own configuration from default paths. If not provided, the
        Controller init method will create a CtlConfig object instance
        automatically and load it with values from default configuration file
        paths.
    :type config: :py:class:`lnst.Controller.Config.CtlConfig`

    :param pools:
        a list of pool names to restrict the used pool directories
    :type pools: List[str] (default [])

    :param pool_checks:
        if False, will disable checking the online status of Agents
    :type pool_checks: boolean (default True)

    :param debug:
        sets the debug level of LNST
    :type debug: integer (default 0)

    Example::

        lnst_controller = Controller()
        recipe_instance = MyRecipe(test_parameter=123)
        lnst_controller.run(recipe_instance)
    """

    def __init__(
        self,
        poolMgr: Union[AgentPoolManager, ContainerPoolManager] = None,
        mapper=MachineMapper,
        config=None,
        pools=[],
        debug=0,
        **poolMgr_kwargs
    ):
        self._config = self._load_ctl_config(config)
        config = self._config

        mac_pool_range = config.get_option('environment', 'mac_pool_range')
        self._mac_pool = MacPool(mac_pool_range[0], mac_pool_range[1])
        self._log_ctl = LoggingCtl(debug,
                log_dir=config.get_option('environment','log_dir'),
                log_subdir=datetime.datetime.now().
                           strftime("%Y-%m-%d_%H:%M:%S"),
                colours=not config.get_option("colours", "disable_colours"))

        self._msg_dispatcher = MessageDispatcher(self._log_ctl)

        self._network_bridges = {}
        self._mapper = mapper()

        select_pools = {}
        conf_pools = config.get_pools()
        if len(pools) > 0:
            for pool_name in pools:
                if pool_name in conf_pools:
                    select_pools[pool_name] = conf_pools[pool_name]
                elif len(pools) == 1 and os.path.isdir(pool_name):
                    select_pools = {"cmd_line_pool": pool_name}
                else:
                    raise ControllerError("Pool %s does not exist!" % pool_name)
        else:
            select_pools = conf_pools

        if poolMgr is None:
            poolMgr = AgentPoolManager

        self._pools = poolMgr(
            select_pools, self._msg_dispatcher, config, **poolMgr_kwargs
        )

    def run(self, recipe, **kwargs):
        """Execute the provided Recipe

        This method takes care of both finding Agent hosts matching the Recipe
        requirements, provisioning them and calling the *test* method of the
        Recipe object with proper references to the mapped Hosts

        :param recipe:
            an instantiated Recipe object
        :type recipe: :py:class:`lnst.Controller.Recipe.BaseRecipe`

        :param kwargs:
            optional keyword arguments passed to the configured Mapper
        :type kwargs: Dict[str, Any]
        """
        if not isinstance(recipe, BaseRecipe):
            raise ControllerError("recipe argument must be a BaseRecipe instance.")

        recipe_ctl = RecipeControl(self, recipe)
        recipe._set_ctl(recipe_ctl)

        req = recipe.req

        self._mapper.set_pools_manager(self._pools)
        self._mapper.set_requirements(req._to_dict())

        i = 0
        try:
            for match in self._mapper.matches(**kwargs):
                self._log_ctl.set_recipe(recipe.__class__.__name__,
                                         expand="match_%d" % i)
                i += 1

                for line in format_match_description(match).split('\n'):
                    logging.info(line)
                try:
                    self._map_match(match, req, recipe)
                    recipe._init_run(RecipeRun(recipe, match, log_dir=self._log_ctl.get_recipe_log_path(),
                                               log_list=self._log_ctl.get_recipe_log_list()))
                    recipe.test()
                except Exception as exc:
                    if recipe.current_run:
                        recipe.current_run.exception = exc
                    logging.error("Recipe execution terminated by unexpected exception")
                    log_exc_traceback()
                    raise
                finally:
                    self._cleanup_agents()
        finally:
            if isinstance(self._pools, ContainerPoolManager):
                self._pools.cleanup()

    def _map_match(self, match, requested, recipe):
        self._machines = {}
        self._hosts = Hosts()
        pool = self._pools.get_machine_pool(match["pool_name"])
        for m_id, m in list(match["machines"].items()):
            machine = self._machines[m_id] = pool[m["target"]]

            setattr(self._hosts, m_id, Host(machine))
            host = getattr(self._hosts, m_id)

            machine.set_id(m_id)
            machine.set_mapped(True)
            self._prepare_machine(machine)

            for if_id, i in list(m["interfaces"].items()):
                host.map_device(if_id, i)

            if match["virtual"]:
                req_host = getattr(requested, m_id)
                for name, dev in req_host:
                    new_virt_dev = VirtualDevice(network=dev.label,
                                    driver=getattr(dev.params, "driver", None),
                                    hwaddr=getattr(dev.params, "hwaddr", None))
                    setattr(host, name, new_virt_dev)
                    new_virt_dev._enable()

            machine.start_recipe(recipe)

    def _prepare_machine(self, machine):
        self._log_ctl.add_agent(machine.get_id())
        machine.set_mac_pool(self._mac_pool)
        machine.set_network_bridges(self._network_bridges)

        machine.prepare_machine()

    def _cleanup_agents(self):
        if self._machines == None:
            return

        for m_id, machine in list(self._machines.items()):
            try:
                machine.cleanup()
            except:
                #TODO report errors during deconfiguration as FAIL!!
                log_exc_traceback()
            finally:
                machine.stop_recipe()
                for dev in list(machine._device_database.values()):
                    if isinstance(dev, VirtualDevice):
                        dev._destroy()

                #clean-up agent logger
                self._log_ctl.remove_agent(m_id)
                machine.set_mapped(False)

        self._machines.clear()

        # remove dynamically created bridges
        for bridge in list(self._network_bridges.values()):
            bridge.cleanup()
        self._network_bridges = {}

    def _load_ctl_config(self, config):
        if isinstance(config, CtlConfig):
            return config
        else:
            config = CtlConfig()

            usr_cfg = os.path.expanduser('~/.lnst/lnst-ctl.conf')
            if os.path.isfile(usr_cfg):
                config.load_config(usr_cfg)
            else:
                usr_cfg_dir = os.path.dirname(usr_cfg)
                pool_dir = usr_cfg_dir + "/pool"
                mkdir_p(pool_dir)
                global_pools = config.get_section("pools")
                if (len(global_pools) == 0):
                    config.add_pool("default", pool_dir, usr_cfg)
                with open(usr_cfg, 'w') as f:
                    f.write(config.dump_config())

            dirname = os.path.dirname(sys.argv[0])
            gitcfg = os.path.join(dirname, "lnst-ctl.conf")
            if os.path.isfile(gitcfg):
                config.load_config(gitcfg)

            return config
