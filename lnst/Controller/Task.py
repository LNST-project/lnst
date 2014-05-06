"""
This module contains the API for python tasks.

Copyright 2013 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

# The handle to be imported from each task
ctl = None

class TaskError(Exception): pass

class ControllerAPI(object):
    """ An API class representing the controller. """

    def __init__(self, ctl, hosts):
        self._ctl = ctl
        self._hosts = hosts
        self._result = True

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

        host = self._hosts[host_id]
        return HostAPI(self, host_id, host)

    def get_module(self, name, **kwargs):
        """
            Initialize a module to be run on a host.

            :param name: name of the module
            :type name: string

            :return: The module handle.
            :rtype: ModuleAPI
        """
        return ModuleAPI(name, kwargs)

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

class HostAPI(object):
    """ An API class representing a host machine. """

    def __init__(self, ctl, host_id, host):
        self._ctl = ctl
        self._id = host_id
        self._m = host

        self._bg_id_seq = 0

    def config(self, option, value, persistent=False):
        """
            Configure an option in /sys or /proc on the host.

            :param option: A path within /sys or /proc.
            :type option: string
            :param value: Value to be set.
            :type value: string
            :param persistent: A flag.
            :type persistent: bool

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
        return ProcessAPI(self._ctl, self._id, cmd_res, bg_id)

    def get_devname(self, interface_id):
        """
            Returns devname of the interface.

            :param interface_id: which interface
            :type interface_id: string

            :return: Device name (e.g., eth0).
            :rtype: str
        """
        iface = self._m.get_interface(interface_id)
        return Devname(iface)

    def get_hwaddr(self, interface_id):
        """
            Returns hwaddr of the interface.

            :param interface_id: which interface
            :type interface_id: string

            :return: HW address (e.g., 00:11:22:33:44:55:FF).
            :rtype: str
        """
        iface = self._m.get_interface(interface_id)
        return Hwaddr(iface)

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
        iface = self._m.get_interface(interface_id)
        return IpAddr(iface, addr_number)

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
        iface = self._m.get_interface(interface_id)
        return Prefix(iface, addr_number)

    def sync_resources(self, modules=[], tools=[]):
        res_table = self._ctl._ctl._resource_table
        sync_table = {'module': {}, 'tools': {}}
        for mod in modules:
            if mod in res_table['module']:
                sync_table['module'][mod] = res_table['module'][mod]
            else:
                msg = "Module '%s' not found on the controller"\
                        % mod
                raise TaskError(msg, cmd)

        for tool in tools:
            if tool in res_table['tools']:
                sync_table['tools'][tool] = res_table['tools'][tool]
            else:
                msg = "Tool '%s' not found on the controller"\
                        % tool
                raise TaskError(msg, cmd)

        self._m.sync_resources(sync_table)

class ModuleAPI(object):
    """ An API class representing a module. """

    def __init__(self, module_name, options):
        self._name = module_name

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

    def __init__(self, ctl, h_id, cmd_res, bg_id):
        self._ctl = ctl
        self._host = h_id
        self._cmd_res = cmd_res
        self._bg_id = bg_id

    def passed(self):
        """
            Returns a boolean result of the process.

            :return: True if the command passed.
            :rtype: bool
        """
        return self.cmd_res["passed"]

    def get_result(self):
        """
            Returns the whole comand result.

            :return: Command result data.
            :rtype: dict
        """
        return self.cmd_res

    def wait(self):
        """ Blocking wait until the command returns. """
        if self._bg_id:
            cmd = {"host": self._host,
                   "type": "wait",
                   "proc_id": self._bg_id}
            self._res = self._ctl._run_command(cmd)

    def intr(self):
        """ Interrupt the command. """
        if self._bg_id:
            cmd = {"host": self._host,
                   "type": "intr",
                   "proc_id": self._bg_id}
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
                   "proc_id": self._bg_id}
            self._res = self._ctl._run_command(cmd)

class ValueAPI(object):
    def __init__(self, iface):
        self._iface = iface

    def _resolve(self):
        pass

    def __str__(self):
        return str(self._resolve())

class IpAddr(ValueAPI):
    def __init__(self, iface, addr=0):
        self._iface = iface
        self._addr = addr

    def _resolve(self):
        return self._iface.get_address(self._addr)

class Hwaddr(ValueAPI):
    def _resolve(self):
        return self._iface.get_hwaddr()

class Devname(ValueAPI):
    def _resolve(self):
        return self._iface.get_devname()

class Prefix(ValueAPI):
    def __init__(self, iface, addr=0):
        self._iface = iface
        self._addr = addr

    def _resolve(self):
        return self._iface.get_prefix(self._addr)
