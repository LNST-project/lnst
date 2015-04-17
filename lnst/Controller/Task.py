"""
This module contains the API for python tasks.

Copyright 2013 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

from lnst.Controller.PerfRepo import PerfRepoRESTAPI
from lnst.Controller.PerfRepo import PerfRepoTestExecution
from lnst.Controller.PerfRepo import PerfRepoValue
from lnst.Common.Utils import dot_to_dict, dict_to_dot, list_to_dot

# The handle to be imported from each task
ctl = None

class TaskError(Exception): pass

class ControllerAPI(object):
    """ An API class representing the controller. """

    def __init__(self, ctl, hosts):
        self._ctl = ctl
        self._result = True

        self._perf_repo_api = PerfRepoAPI()

        self._hosts = {}
        for host_id, host in hosts.iteritems():
            self._hosts[host_id] = HostAPI(self, host_id, host)

    def _run_command(self, command):
        """
            An internal wrapper that allows keeping track of the
            results of the commands within the task.

            Please, don't use this.
        """
        res = self._ctl._run_command(command)
        self._result = self._result and res["passed"]
        return res

    def get_host(self, host_id):
        """
            Get an API handle for the host from the recipe spec with
            a specific id.

            :param host_id: id of the host as defined in the recipe
            :type host_id: string

            :return: The host handle.
            :rtype: HostAPI

            :raises TaskError: If there is no host with such id.
        """
        if host_id not in self._hosts:
            raise TaskError("Host '%s' not found." % host_id)

        return self._hosts[host_id]

    def get_hosts(self):
        return self._hosts

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

    def get_alias(self, alias):
        """
            Get the value of user defined alias.

            :param alias: name of user defined alias
            :type alias: string

            :return: value of a user defined alias
            :rtype: string
        """
        return self._ctl._get_alias(alias)

    def connect_PerfRepo(self, hostname, username, password):
        if not self._perf_repo_api.connected():
            self._perf_repo_api.connect(hostname, username, password)
        return self._perf_repo_api

    def get_configuration(self):
        return self._ctl._recipe["machines"]

    def get_mapping(self):
        match = self._ctl.get_pool_match()
        mapping = []
        for m_id, m in match["machines"].iteritems():
            machine = {}
            machine["id"] = m_id
            machine["pool_id"] = m["target"]
            machine["hostname"] = m["hostname"]
            machine["interface"] = []
            for i_id, i in m["interfaces"].iteritems():
                interface = {}
                interface["id"] = i_id
                interface["pool_id"] = i["target"]
                interface["hwaddr"] = i["hwaddr"]
                machine["interface"].append(interface)
            mapping.append(machine)
        return mapping

class HostAPI(object):
    """ An API class representing a host machine. """

    def __init__(self, ctl, host_id, host):
        self._ctl = ctl
        self._id = host_id
        self._m = host

        self._interfaces = {}
        for i in self._m.get_interfaces():
            if i.get_id() is None:
                continue
            self._interfaces[i.get_id()] = InterfaceAPI(i)

        self._bg_id_seq = 0

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

            :return: A handle for process.
            :rtype: ProcessAPI
        """
        cmd = {"host": str(self._id)}
        bg_id = None
        cmd["netns"] = None

        for arg, argval in kwargs.iteritems():
            if arg == "bg" and argval == True:
                self._bg_id_seq += 1
                cmd["bg_id"] = bg_id = self._bg_id_seq
            elif arg == "expect":
                if str(argval) not in ["pass", "fail"]:
                    msg = "Unrecognised value of the expect attribute (%s)." \
                          % argval
                    raise TaskError(msg)

                cmd["expect"] = argval == "pass"
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
                cmd["save_output"] = argval
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

    def get_interfaces(self):
        return self._interfaces

    def get_interface(self, interface_id):
        return self._interfaces[interface_id]

    def get_devname(self, interface_id):
        """
            Returns devname of the interface.

            :param interface_id: which interface
            :type interface_id: string

            :return: Device name (e.g., eth0).
            :rtype: str
        """
        iface = self._interfaces[interface_id]
        return iface.get_devname()

    def get_hwaddr(self, interface_id):
        """
            Returns hwaddr of the interface.

            :param interface_id: which interface
            :type interface_id: string

            :return: HW address (e.g., 00:11:22:33:44:55:FF).
            :rtype: str
        """
        iface = self._interfaces[interface_id]
        return iface.get_hwaddr()

    def get_ip(self, interface_id, addr_number=0):
        """
            Returns an IP address of the interface.

            :param interface_id: which interface
            :type interface_id: string

            :param interface_id: which address
            :type interface_id: int

            :return: IP address (e.g., 192.168.1.10).
            :rtype: str
        """
        iface = self._interfaces[interface_id]
        return iface.get_ip_addr(addr_number)

    def get_prefix(self, interface_id, addr_number=0):
        """
            Returns an IP address prefix (netmask)
            of the interface.

            :param interface_id: which interface
            :type interface_id: string

            :param interface_id: which address
            :type interface_id: int

            :return: netmask (e.g., 24).
            :rtype: str
        """
        iface = self._interfaces[interface_id]
        return iface.get_ip_prefix(addr_number)

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

class InterfaceAPI(object):
    def __init__(self, interface):
        self._if = interface

    def get_id(self):
        return self._if.get_id()

    def get_network(self):
        return self._if.get_network()

    def get_devname(self):
        return VolatileValue(self._if.get_devname)

    def get_hwaddr(self):
        return VolatileValue(self._if.get_hwaddr)

    def get_ip_addr(self, ip_index):
        return VolatileValue(self._if.get_address, ip_index)

    def get_ip_addrs(self):
        return VolatileValue(self._if.get_addresses)

    def get_ip_prefix(self, ip_index):
        return VolatileValue(self._if.get_prefix, ip_index)

class ModuleAPI(object):
    """ An API class representing a module. """

    def __init__(self, module_name, options={}):
        self._name = module_name

        self._opts = {}
        for opt, val in options.iteritems():
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
        for opt, val in options.iteritems():
            self._opts[opt] = []
            if type(val) == list:
                for v in val:
                    self._opts[opt].append({"value": str(v)})
            else:
                self._opts[opt].append({"value": str(val)})

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

    def wait(self):
        """ Blocking wait until the command returns. """
        if self._bg_id:
            cmd = {"host": self._host,
                   "type": "wait",
                   "proc_id": self._bg_id,
                   "netns": self._netns}
            self._res = self._ctl._run_command(cmd)

    def intr(self):
        """ Interrupt the command. """
        if self._bg_id:
            cmd = {"host": self._host,
                   "type": "intr",
                   "proc_id": self._bg_id,
                   "netns": self._netns}
            self._res = self._ctl._run_command(cmd)

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
            self._res = self._ctl._run_command(cmd)

class VolatileValue(object):
    def __init__(self, func, *args, **kwargs):
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def get_val(self):
        return self._func(*self._args, **self._kwargs)

    def __str__(self):
        return str(self.get_val())

class PerfRepoAPI(object):
    def __init__(self):
        self._rest_api = None

    def connected(self):
        return self._rest_api is not None

    def connect(self, hostname, username, password):
        self._rest_api = PerfRepoRESTAPI(hostname, username, password)

    def new_result(self, testUid, name):
        result = PerfRepoResult(testUid, name)
        return result

    def save_result(self, result):
        if not isinstance(result, PerfRepoResult):
            raise TaskError("Parameter result must be an instance "\
                            "of PerfRepoResult")
        elif self._rest_api is None:
            raise TaskError("Not connected to PerfRepo.")
        else:
            self._rest_api.testExecution_create(result.get_testExecution())

    def get_baseline(self, report_id):
        report = self._rest_api.report_get_by_id(report_id)
        return report.get_baseline()

    def compare_to_baseline(self, result, report_id, metric_name):
        baseline = self.get_baseline(report_id)
        baseline_exec_id = baseline["execId"]
        baseline_testExec = self._rest_api.testExecution_get(baseline_exec_id)
        result_testExec = result.get_testExecution()

        return self.compare_testExecutions(result_testExec,
                                           baseline_testExec,
                                           metric_name)

    def compare_testExecutions(self, first, second, metric_name):
        first_value = first.get_value(metric_name)
        first_min = first.get_value(metric_name + "_min")
        first_max = first.get_value(metric_name + "_max")

        second_value = second.get_value(metric_name)
        second_min = second.get_value(metric_name + "_min")
        second_max = second.get_value(metric_name + "_max")

        comp = second_value.get_comparator()
        print second_min.get_result(),  first_max.get_result()
        if comp == "HB":
            if second_min.get_result() > first_max.get_result():
                return False
            return True
        elif comp == "LB":
            if first_min.get_result() > second_max.get_result():
                return False
            return True
        else:
            return False
        return False

class PerfRepoResult(object):
    def __init__(self, testUid, name):
        self._testExecution = PerfRepoTestExecution()
        self._testExecution.set_testUid(testUid)
        self._testExecution.set_name(name)
        self.set_configuration(ctl.get_configuration())
        self.set_mapping(ctl.get_mapping())

    def add_value(self, val_name, value):
        perf_value = PerfRepoValue()
        perf_value.set_metricName(val_name)
        perf_value.set_result(value)

        self._testExecution.add_value(perf_value)

    def set_configuration(self, configuration=None):
        if configuration is None:
            configuration = ctl.get_configuration()
        for pair in list_to_dot(configuration, "configuration.", "machine"):
            self._testExecution.add_parameter(pair[0], pair[1])

    def set_mapping(self, mapping=None):
        if mapping is None:
            mapping = ctl.get_mapping()
        for pair in list_to_dot(mapping, "mapping.", "machine"):
            self._testExecution.add_parameter(pair[0], pair[1])

    def set_tags(self, tags):
        for tag in tags:
            self._testExecution.add_tag(tag)

    def get_testExecution(self):
        return self._testExecution
