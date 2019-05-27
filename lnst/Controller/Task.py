"""
This module contains the API for python tasks.

Copyright 2013 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import hashlib
import re
import logging
from lnst.Common.Utils import dict_to_dot, list_to_dot, deprecated
from lnst.Common.Config import lnst_config
from lnst.Controller.XmlTemplates import XmlTemplateError
from lnst.Common.Path import Path
from lnst.Controller.PerfRepoMapping import PerfRepoMapping
from lnst.Controller.Common import ControllerError
from lnst.Common.Utils import Noop

try:
    from perfrepo import PerfRepoRESTAPI
    from perfrepo import PerfRepoTestExecution
    from perfrepo import PerfRepoValue
except:
    PerfRepoRESTAPI = None
    PerfRepoTestExecution = None
    PerfRepoValue = None

# The handle to be imported from each task
ctl = None

def get_alias(alias, default=None):
    return ctl.get_alias(alias, default)

def get_mreq():
    return ctl.get_mreq()

def wait(seconds):
    return ctl.wait(seconds)

def get_module(name, options={}):
    return ctl.get_module(name, options)

def breakpoint():
    if not ctl.breakpoints:
        return
    logging.info("Breakpoint reached. Press enter to continue.")
    eval(input(""))

def add_host(params={}):
    m_id = ctl.gen_m_id()
    ctl.mreq[m_id] = {'interfaces' : {}, 'params' : params}
    handle =  HostAPI(ctl, m_id)
    ctl.add_host(m_id, handle)
    return handle

def match():
    ctl.cleanup_slaves()

    if ctl.first_run:
        ctl.first_run = False
        ctl.set_machine_requirements()

        if ctl.prepare_test_env():
            if ctl.run_mode == "match_setup":
                return False
            if ctl.packet_capture():
                ctl.start_packet_capture()
            return True
    else:
        if ctl._ctl._multi_match:
            if ctl.prepare_test_env():
                if ctl.run_mode == "match_setup":
                    return False
                if ctl.packet_capture():
                    ctl.start_packet_capture()
                return True
            else:
                return False
        else:
            return False


class TaskError(ControllerError):
    pass

class ControllerAPI(object):
    """ An API class representing the controller. """

    def __init__(self, ctl):
        self._ctl = ctl
        self.run_mode = ctl.run_mode
        self.breakpoints = ctl.breakpoints
        self._result = True
        self.first_run = True
        self._m_id_seq = 0
        self.mreq = {}

        self._perf_repo_api = PerfRepoAPI()

        self._hosts = {}

    def get_mreq(self):
        return self.mreq

    def cleanup_slaves(self):
       self._ctl._cleanup_slaves()

    def set_machine_requirements(self):
        self._ctl.set_machine_requirements()

    def packet_capture(self):
        return self._ctl._packet_capture

    def start_packet_capture(self):
        self._ctl._start_packet_capture()

    def prepare_test_env(self):
        return self._ctl.prepare_test_env()

    def gen_m_id(self):
        self._m_id_seq += 1
        return "m_id_%s" % self._m_id_seq

    def add_host(self, host_id, handle):
        self._hosts[host_id] = handle

    def init_hosts(self, hosts):
        for host_id, host in list(hosts.items()):
            self._hosts[host_id].init_host(host)

    def _run_command(self, command):
        """
            An internal wrapper that allows keeping track of the
            results of the commands within the task.

            Please, don't use this.
        """
        res = self._ctl._run_command(command)
        self._result = self._result and res["passed"]
        return res

    def get_module(self, name, options={}):
        """
            Initialize a module to be run on a host.

            :param name: name of the module
            :type name: string

            :return: The module handle.
            :rtype: ModuleAPI
        """
        return ModuleAPI(name, options)

    def wait(self, seconds):
        """
            The controller will wait for a specific amount of seconds.

            :param seconds: how long
            :type seconds: float

            :return: Command result (always passes).
            :rtype: dict
        """
        cmd = {"type": "ctl_wait", "seconds": int(seconds)}
        return self._ctl._run_command(cmd)

    def get_alias(self, alias, default=None):
        """
            Get the value of user defined alias.

            :param alias: name of user defined alias
            :type alias: string

            :return: value of a user defined alias
            :rtype: string
        """
        try:
            val =  self._ctl._get_alias(alias)
            if val is None:
                return default
            else:
                return val
        except XmlTemplateError:
            return default

    def get_aliases(self):
        """
            Get all user defined aliases.

            :return: names and values of a user defined aliases
            :rtype: dict
        """
        return self._ctl._get_aliases()

    def connect_PerfRepo(self, mapping_file, url=None, username=None, password=None):
        if not self._perf_repo_api.connected():
            if url is None:
                url = lnst_config.get_option("perfrepo", "url")
            if username is None:
                username = lnst_config.get_option("perfrepo", "username")
            if password is None:
                password = lnst_config.get_option("perfrepo", "password")

            if not url:
                logging.warn("No PerfRepo URL specified in config file")
            if not username:
                logging.warn("No PerfRepo username specified in config file")
            if not password:
                logging.warn("No PerfRepo password specified in config file")
            if url and username and password:
                self._perf_repo_api.connect(url, username, password)

            root = Path(None, self._ctl._recipe_path).get_root()
            path = Path(root, mapping_file)
            self._perf_repo_api.load_mapping(path)

            if not self._perf_repo_api.connected():
                if PerfRepoRESTAPI is None:
                    logging.warn("Python PerfRepo library not found.")
                logging.warn("Connection to PerfRepo incomplete, further "\
                             "PerfRepo commands will be ignored.")
        return self._perf_repo_api

    def get_configuration(self):
        machines = self._ctl._machines
        configuration = {}
        for m_id, m in list(machines.items()):
            configuration["machine_"+m_id] = m.get_configuration()
        return configuration

    def get_mapping(self):
        match = self._ctl.get_pool_match()
        mapping = []
        for m_id, m in list(match["machines"].items()):
            machine = {}
            machine["id"] = m_id
            machine["pool_id"] = m["target"]
            machine["hostname"] = m["hostname"]
            machine["interface"] = []
            for i_id, i in list(m["interfaces"].items()):
                interface = {}
                interface["id"] = i_id
                interface["pool_id"] = i["target"]
                interface["hwaddr"] = i["hwaddr"]
                machine["interface"].append(interface)
            mapping.append(machine)
        return mapping

class HostAPI(object):
    """ An API class representing a host machine. """

    def __init__(self, ctl, host_id):
        self._ctl = ctl
        self._id = host_id
        self._m = None

        self._ifaces = {}
        self._if_id_seq = 0
        self._bg_id_seq = 0

    def _gen_if_id(self):
        self._if_id_seq += 1
        return "if_id_%s" % self._if_id_seq

    def init_host(self, host):
        self._m = host
        self.init_ifaces()

    def init_ifaces(self):
        for interface in self._m.get_interfaces():
            if interface.get_id() is None:
                continue
            self._ifaces[interface.get_id()].init_iface(interface)

    def add_interface(self, label, netns=None, params=None):
        m_id = self.get_id()
        if_id = self._gen_if_id()

        self._ctl.mreq[m_id]['interfaces'][if_id] = {}
        self._ctl.mreq[m_id]['interfaces'][if_id]['network'] = label
        self._ctl.mreq[m_id]['interfaces'][if_id]['netns'] = netns

        if params:
            self._ctl.mreq[m_id]['interfaces'][if_id]['params'] = params
        else:
            self._ctl.mreq[m_id]['interfaces'][if_id]['params'] = {}

        self._ifaces[if_id] = InterfaceAPI(None, self)
        return self._ifaces[if_id]

    def get_id(self):
        return self._id

    def get_configuration(self):
        return self._m.get_configuration()

    def config(self, option, value, persistent=False, netns=None):
        """
            Configure an option in /sys or /proc on the host.

            :param option: A path within /sys or /proc.
            :type option: string
            :param value: Value to be set.
            :type value: string
            :param persistent: A flag.
            :type persistent: bool
            :param netns: LNST created namespace to configure.
            :type netns: string

            :return: Command result.
            :rtype: dict
        """
        cmd = {"host": str(self._id), "type": "config"}
        cmd["options"] = [{"name": option, "value": value}]
        cmd["persistent"] = persistent
        cmd["netns"] = netns

        return self._ctl._run_command(cmd)

    def run(self, what, **kwargs):
        """
            Configure an option in /sys or /proc on the host.

            :param what: What should be run on the host.
            :type what: str or ModuleAPI

            :param bg: Run in background flag.
            :type bg: bool
            :param expect: "pass" or "fail".
            :type expect: string
            :param timeout: A time limit in seconds.
            :type timeout: int
            :param tool: Run from a tool (the same as 'from' in XML).
            :type tool: string
            :param json: Process JSON output into dictionary.
            :type json: bool

            :return: A handle for process.
            :rtype: ProcessAPI
        """
        cmd = {"host": str(self._id)}
        bg_id = None
        cmd["netns"] = None

        for arg, argval in list(kwargs.items()):
            if arg == "bg" and argval == True:
                self._bg_id_seq += 1
                cmd["bg_id"] = bg_id = self._bg_id_seq
            elif arg == "bg" and argval == False:
                continue
            elif arg == "expect":
                if str(argval) not in ["pass", "fail"]:
                    msg = "Unrecognised value of the expect attribute (%s)." \
                          % argval
                    raise TaskError(msg)

                cmd["expect"] = argval == "pass"
            elif arg == "fail_expected":
                cmd["expect"] = not argval
            elif arg == "timeout":
                try:
                    cmd["timeout"] = int(argval)
                except ValueError:
                    msg = "Timeout must be integer, not '%s'." % argval
                    raise TaskError(msg)
            elif arg == "tool":
                if type(what) == str:
                    cmd["from"] = str(argval)
                else:
                    msg = "Argument 'tool' not valid when running modules."
                    raise TaskError(msg)
            elif arg == "desc":
                cmd["desc"] = argval
            elif arg == "netns":
                cmd["netns"] = argval
            elif arg == "save_output":
                pass # now ignored as output is saved always
            elif arg == "json":
                cmd["json"] = argval
            else:
                msg = "Argument '%s' not recognised by the run() method." % arg
                raise TaskError(msg)

        if type(what) == ModuleAPI:
            cmd["type"] = "test"
            cmd["module"] = what._name
            cmd["options"] = what._opts
        elif type(what) == str:
            cmd["type"] = "exec"
            cmd["command"] = str(what)
        else:
            raise TaskError("Unable to run '%s'." % str(what))

        cmd_res = self._ctl._run_command(cmd)
        return ProcessAPI(self._ctl, self._id, cmd_res, bg_id, cmd["netns"])

    def sync_resources(self, modules=[], tools=[]):
        res_table = self._ctl._ctl._resource_table
        sync_table = {'module': {}, 'tools': {}}
        for mod in modules:
            if mod in res_table['module']:
                sync_table['module'][mod] = res_table['module'][mod]
            else:
                msg = "Module '%s' not found on the controller"\
                        % mod
                raise TaskError(msg)

        for tool in tools:
            if tool in res_table['tools']:
                sync_table['tools'][tool] = res_table['tools'][tool]
            else:
                msg = "Tool '%s' not found on the controller"\
                        % tool
                raise TaskError(msg)

        self._m.sync_resources(sync_table)

    def _add_iface(self, if_type, if_id, netns, ip, options, slaves):
        interface = self._m.new_soft_interface(if_id, if_type)
        if_id = interface.get_id()
        iface = InterfaceAPI(interface, self)
        self._ifaces[if_id] = iface

        if slaves:
            for slave in slaves:
                if type(slave) == type(()):
                    slave_iface = slave[0]
                    slave_options = slave[1]
                    for key in slave_options:
                        interface.set_slave_option(slave_iface.get_id(),
                                                   key, slave_options[key])
                else:
                    slave_iface = slave
                interface.add_slave(slave_iface._if)

        if ip:
            interface.add_address(ip)

        if options:
            for key in options:
                interface.set_option(key, options[key])

        if netns:
            interface.set_netns(netns)

        interface.configure()
        interface.up()

        self._m.wait_interface_init()

        return iface

    def _remove_iface(self, iface):
        interface = iface._if
        interface.deconfigure()
        interface.cleanup()
        if_id = interface.get_id()
        self._m.remove_interface(if_id)
        self._ifaces.pop(if_id)

    def create_bond(self, if_id=None, netns=None, ip=None,
                    options=None, slaves=None):
        return self._add_iface("bond", if_id, netns, ip, options, slaves)

    def create_bridge(self, if_id=None, netns=None, ip=None,
                      options=None, slaves=None):
        return self._add_iface("bridge", if_id, netns, ip, options, slaves)

    def create_team(self, config=None, if_id=None, netns=None, ip=None,
                    slaves=None):
        out_slaves = []
        for slave in slaves:
            if type(slave) == type(()):
                slave_iface = slave[0]
                slave_config = slave[1]
                out_slaves.append((slave_iface,
                                   {"teamd_port_config": slave_config}))
            else:
                out_slaves.append(slave)

        options = {}
        if config:
            options["teamd_config"] = config

        return self._add_iface("team", if_id, netns, ip, options, out_slaves)

    def create_vlan(self, realdev_iface, vlan_tci, if_id=None, netns=None, ip=None):
        return self._add_iface("vlan", if_id, netns, ip, {"vlan_tci": vlan_tci},
                               [realdev_iface])

    def create_vxlan(self, vxlan_id, realdev_iface=None, group_ip=None,
                     remote_ip=None, if_id=None, netns=None, ip=None, options={}):
        if group_ip is None and remote_ip is None:
            raise TaskError("Either group_ip or remote_ip must be specified.")

        options.update({"id": vxlan_id,
                        "group_ip": group_ip,
                        "remote_ip": remote_ip})
        if realdev_iface is not None:
            slaves = [realdev_iface]
        else:
            slaves = []

        return self._add_iface("vxlan", if_id, netns, ip, options, slaves)

class DeviceAPI(object):
    def __init__(self, net_device, host):
        self._dev = net_device
        self._host = host

    def get_if_index(self):
        return self._dev.get_if_index()

    def get_hwaddr(self):
        return self._dev.get_hwaddr()

    def get_devname(self):
        return self._dev.get_name()

    def get_ips(self, selector={}):
        return self._dev.get_ip_addrs(selector)

    def get_ip(self, num, selector={}):
        return self._dev.get_ip_addr(num, selector)

    def get_ifi_type(self):
        return self._dev.get_ifi_type()

    def get_state(self):
        return self._dev.get_state()

    # def get_master(self):
        # return self._dev.get_master()

    def get_slaves(self):
        return self._dev.get_slaves()

    def get_netns(self):
        return self._dev.get_netns()

    # def get_peer(self):
        # return self._dev.get_peer()

    def get_mtu(self):
        return self._dev.get_mtu()

    def set_mtu(self, mtu):
        return self._dev.set_mtu(mtu)

    def get_driver(self):
        return self._dev.get_driver()

    def get_devlink_name(self):
        return self._dev.get_devlink_name()

    def get_devlink_port_name(self):
        return self._dev.get_devlink_port_name()

class InterfaceAPI(object):
    def __init__(self, interface, host):
        self._if = interface
        self._host = host

    def init_iface(self, interface):
        self._if = interface

    def get_id(self):
        return self._if.get_id()

    def get_type(self):
        return self._if.get_type()

    def get_network(self):
        return self._if.get_network()

    def get_driver(self):
        return VolatileValue(self._if.get_driver)

    def get_devname(self):
        return VolatileValue(self._if.get_devname)

    def get_hwaddr(self):
        return VolatileValue(self._if.get_hwaddr)

    def get_ip(self, ip_index=0, selector={}):
        return VolatileValue(self._if.get_address, ip_index)

    def get_ips(self, selector={}):
        return VolatileValue(self._if.get_addresses)

    def get_prefix(self, ip_index=0):
        return VolatileValue(self._if.get_prefix, ip_index)

    def get_mtu(self):
        return VolatileValue(self._if.get_mtu)

    def set_mtu(self, mtu):
        return self._if.set_mtu(mtu)

    def link_stats(self):
        return self._if.link_stats()

    def set_link_up(self):
        return self._if.set_link_up()

    def set_link_down(self):
        return self._if.set_link_down()

    def get_host(self):
        return self._host

    def get_netns(self):
        return self._if.get_netns()

    def reset(self, ip=None, netns=None):
        self._if.down()
        self._if.deconfigure()

        if ip:
            self._if.add_address(ip)

        if netns:
            self._if.set_netns(netns)

        self._if.configure()
        self._if.up()

    def set_addresses(self, ips):
        self._if.set_addresses(ips)

    def enable_multicast(self):
        self._if.add_route("224.0.0.0/4")

    def disable_multicast(self):
        self._if.del_route("224.0.0.0/4")

    def destroy(self):
        self._host._remove_iface(self)

    def add_br_vlan(_self, vlan_tci, pvid=False, untagged=False,
                    self=False, master=False):
        _self._if.add_br_vlan({"vlan_id": vlan_tci, "pvid": pvid,
                               "untagged": untagged,
                               "self": self, "master": master})

    def del_br_vlan(_self, vlan_tci, pvid=False, untagged=False,
                    self=False, master=False):
        _self._if.del_br_vlan({"vlan_id": vlan_tci, "pvid": pvid,
                               "untagged": untagged,
                               "self": self, "master": master})

    def get_br_vlans(self):
        return self._if.get_br_vlans()

    def add_br_fdb(_self, hwaddr, self=False, master=False, vlan_tci=None):
        _self._if.add_br_fdb({"hwaddr": hwaddr, "self": self, "master": master,
                              "vlan_id": vlan_tci})

    def del_br_fdb(_self, hwaddr, self=False, master=False, vlan_tci=None):
        _self._if.del_br_fdb({"hwaddr": hwaddr, "self": self, "master": master,
                              "vlan_id": vlan_tci})

    def get_br_fdbs(self):
        return self._if.get_br_fdbs()

    def set_br_learning(_self, on=True, self=False, master=False):
        _self._if.set_br_learning({"on": on, "self": self, "master": master})

    def set_br_learning_sync(_self, on=True, self=False, master=False):
        _self._if.set_br_learning_sync({"on": on, "self": self,
                                        "master": master})

    def set_br_flooding(_self, on=True, self=False, master=False):
        _self._if.set_br_flooding({"on": on, "self": self, "master": master})

    def set_br_state(_self, state, self=False, master=False):
        _self._if.set_br_state({"state": state, "self": self, "master": master})

    def set_speed(self, speed):
        return self._if.set_speed(speed)

    def set_autoneg(self):
        return self._if.set_autoneg()

    def slave_add(self, slave_id):
        return self._if.slave_add(slave_id)

    def slave_del(self, slave_id):
        return self._if.slave_del(slave_id)

    def get_devlink_name(self):
        return self._if.get_devlink_name()

    def get_devlink_port_name(self):
        return self._if.get_devlink_port_name()

class ModuleAPI(object):
    """ An API class representing a module. """

    def __init__(self, module_name, options={}):
        self._name = module_name

        self._opts = {}
        for opt, val in list(options.items()):
            self._opts[opt] = []
            if type(val) == list:
                for v in val:
                    self._opts[opt].append({"value": str(v)})
            else:
                self._opts[opt].append({"value": str(val)})

    def get_options(self):
        return self._opts

    def set_options(self, options):
        self._opts = {}
        for opt, val in list(options.items()):
            self._opts[opt] = []
            if type(val) == list:
                for v in val:
                    self._opts[opt].append({"value": str(v)})
            else:
                self._opts[opt].append({"value": str(val)})

    def update_options(self, options):
        for opt, val in list(options.items()):
            self._opts[opt] = []
            if type(val) == list:
                for v in val:
                    self._opts[opt].append({"value": str(v)})
            else:
                self._opts[opt].append({"value": str(val)})

    def unset_option(self, option_name):
        if option_name in self._opts:
            del self._opts[option_name]

class ProcessAPI(object):
    """ An API class representing either a running or finished process. """

    def __init__(self, ctl, h_id, cmd_res, bg_id, netns):
        self._ctl = ctl
        self._host = h_id
        self._cmd_res = cmd_res
        self._bg_id = bg_id
        self._netns = netns

    def passed(self):
        """
            Returns a boolean result of the process.

            :return: True if the command passed.
            :rtype: bool
        """
        return self._cmd_res["passed"]

    def get_result(self):
        """
            Returns the whole comand result.

            :return: Command result data.
            :rtype: dict
        """
        return self._cmd_res

    def out(self):
        """
            Returns the whole command result stdout.

            :return: Command result stdout.
            :rtype: str
        """
        return self.get_result()["res_data"]["stdout"]

    def wait(self):
        """ Blocking wait until the command returns. """
        if self._bg_id:
            cmd = {"host": self._host,
                   "type": "wait",
                   "proc_id": self._bg_id,
                   "netns": self._netns}
            self._cmd_res = self._ctl._run_command(cmd)

    def intr(self):
        """ Interrupt the command. """
        if self._bg_id:
            cmd = {"host": self._host,
                   "type": "intr",
                   "proc_id": self._bg_id,
                   "netns": self._netns}
            self._cmd_res = self._ctl._run_command(cmd)

    def kill(self):
        """
            Kill the command.

            In this case, the command results are disposed. A killed
            command will always be shown as passed. If you would like
            to keep the results, use 'intr' instead.
        """
        if self._bg_id:
            cmd = {"host": self._host,
                   "type": "kill",
                   "proc_id": self._bg_id,
                   "netns": self._netns}
            self._cmd_res = self._ctl._run_command(cmd)

class VolatileValue(object):
    def __init__(self, func, *args, **kwargs):
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def get_val(self):
        return self._func(*self._args, **self._kwargs)

    def __str__(self):
        return str(self.get_val())

