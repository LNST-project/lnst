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

    def __init__(self, ctl, machines):
        self._ctl = ctl
        self._machines = machines
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

    def get_machine(self, machine_id):
        """
            Get an API handle for the machine from the recipe spec with
            a specific id.

            :param machine_id: id of the machine as defined in the recipe
            :type machine_id: string

            :return: The machine handle.
            :rtype: MachineAPI

            :raises TaskError: If there is no machine with such id.
        """
        if machine_id not in self._machines:
            raise TaskError("Machine '%s' not found." % machine_id)

        machine = self._machines[machine_id]
        return MachineAPI(self, machine_id, machine)

    def get_module(self, name, **kwargs):
        """
            Initialize a module to be run on a machine.

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

class MachineAPI(object):
    """ An API class representing a machine. """

    def __init__(self, ctl, machine_id, machine):
        self._ctl = ctl
        self._id = machine_id
        self._m = machine

        self._bg_id_seq = 0

    def config(self, option, value, persistent=False):
        """
            Configure an option in /sys or /proc on the machine.

            :param option: A path within /sys or /proc.
            :type option: string
            :param value: Value to be set.
            :type value: string
            :param persistent: A flag.
            :type persistent: bool

            :return: Command result.
            :rtype: dict
        """
        cmd = {"machine": str(self._id), "type": "config"}
        cmd["options"] = [{"name": option, "value": value}]
        cmd["persistent"] = persistent

        return self._ctl._run_command(cmd)

    def run(self, what, **kwargs):
        """
            Configure an option in /sys or /proc on the machine.

            :param what: What should be run on the machine.
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
        cmd = {"machine": str(self._id)}
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

    def __init__(self, ctl, m_id, cmd_res, bg_id):
        self._ctl = ctl
        self._machine = m_id
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
            cmd = {"machine": self._machine,
                   "type": "wait",
                   "proc_id": self._bg_id}
            self._res = self._ctl._run_command(cmd)

    def intr(self):
        """ Interrupt the command. """
        if self._bg_id:
            cmd = {"machine": self._machine,
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
            cmd = {"machine": self._machine,
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
