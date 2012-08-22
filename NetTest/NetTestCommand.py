"""
This module defines classes of test commands

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import logging
import os
import sys
import signal
import imp
import pickle, traceback
from Common.ExecCmd import exec_cmd, ExecCmdFail

def str_command(command):
    out = ("type (%s), machine_id (%s), value (%s)"
                % (command["type"], command["machine_id"], command["value"]))
    if "timeout" in command:
        out += ", timeout (%d)" % command["timeout"]
    if "bg_id" in command:
        out += ", bg_id (%d)" % command["bg_id"]
    if "desc" in command:
        out += ", desc (%s)" % command["desc"]
    return out

class CommandException(Exception):
    """Base class for client errors."""
    def __init__(self, command):
        self.command = command

    def __str__(self):
        return "CommandException: " + str(self.command)

class BgProcessException(Exception):
    """Base class for client errors."""
    def __init__(self, str):
        self._str = str

    def __str__(self):
        return "BgProcessError: " + self._str

class BGProcesses:
    def __init__(self):
        self._dict = {}

    def add(self, bg_id, pid, pipe):
        if bg_id in self._dict:
            raise Exception
        self._dict[bg_id] = {"pid": pid, "pipe": pipe}

    def get_pid(self, bg_id):
        return self._dict[bg_id]["pid"]

    def get_pipe(self, bg_id):
        return self._dict[bg_id]["pipe"]

    def remove(self, bg_id):
        del self._dict[bg_id]

    def get_bg_process_result(self, bg_id):
        pipe = self.get_pipe(bg_id)
        tmp = os.read(pipe, 4096*10)
        result = pickle.loads(tmp)
        if "Exception" in result:
            raise BgProcessException(result["Exception"])
        os.close(pipe)
        return result

bg_processes = BGProcesses()

def NetTestCommandTest(command):
    test_name = command["value"]
    module_name = "Test%s" % test_name
    fp, pathname, description = imp.find_module("Tests/%s" % module_name)
    module = imp.load_module("Tests/%s" % module_name,
                             fp, pathname, description)
    test_class = getattr(module, module_name)
    return test_class(command)

class NetTestCommandGeneric:
    def __init__(self, command):
        self._command = command
        self._result = None

    def run(self):
        pass

    def set_result(self, result):
        self._result = result

    def get_result(self):
        if not self._result:
            '''
            In case result is not set yet, it most likely means that
            command was killed. So set pass in this case
            '''
            self.set_pass()
        return self._result

    def set_fail(self, err_msg):
        result = {"passed": False, "err_msg": err_msg}
        self.set_result(result)
        return result

    def set_pass(self):
        result = {"passed": True}
        self.set_result(result)
        return result

    def set_handle_intr(self):
        pass

class NetTestCommandExec(NetTestCommandGeneric):
    def run(self):
        try:
            exec_cmd(self._command["value"])
            self.set_pass()
        except ExecCmdFail:
            if "bg_id" in self._command:
                logging.info("Command probably intentionally killed. Passing.")
                self.set_pass()
            else:
                self.set_fail("Command failed to execute")

class NetTestCommandSystemConfig(NetTestCommandGeneric):
    def _retrive_option(self, option):
        cmd_str = "cat %s" % option
        (stdout, stderr) = exec_cmd(cmd_str)
        return stdout.strip()

    def _set_option(self, option, value):
        cmd_str = "echo \"%s\" >%s" % (value, option)
        (stdout, stderr) = exec_cmd(cmd_str)

    def run(self):
        res_data = {}

        # inline version
        if "option" in self._command:
            opt = self._command["option"]
            val = [{"value": self._command["value"]}]
            self._command["options"] = {opt: val}

        for option, opt_data in self._command["options"].iteritems():
            new_values = []
            for record in opt_data:
                new_values.append(record["value"])

            option_abspath = os.path.abspath(option)
            if option_abspath[0:5] != "/sys/" and \
               option_abspath[0:6] != "/proc/":
                err = "Wrong config option %s. Only /proc or /sys paths are allowed." % option
                self.set_fail(err)
                return

            try:
                prev_val = self._retrive_option(option)
                for new_val in new_values:
                    self._set_option(option, new_val)
            except ExecCmdFail:
                self.set_fail("Unable to set %s config option!" % option)
                return

            res_data[option] = {"current_val": new_values[-1],
                                "previous_val": prev_val}

        res = {"passed": True}
        res["res_data"] = res_data
        self.set_result(res)

class NetTestCommandWait(NetTestCommandGeneric):
    def run(self):
        bg_id = int(self._command["value"])
        pid = bg_processes.get_pid(bg_id)
        logging.debug("Waiting for background id \"%d\", pid \"%d\"" % (bg_id, pid))
        os.waitpid(pid, 0)
        result = bg_processes.get_bg_process_result(bg_id)
        bg_processes.remove(bg_id)
        self.set_result(result)

class NetTestCommandIntr(NetTestCommandGeneric):
    def run(self):
        bg_id = int(self._command["value"])
        pid = bg_processes.get_pid(bg_id)
        logging.debug("Interrupting background id \"%d\", pid \"%d\"" % (bg_id, pid))
        os.killpg(os.getpgid(pid), signal.SIGINT)
        os.waitpid(pid, 0)
        result = bg_processes.get_bg_process_result(bg_id)
        bg_processes.remove(bg_id)
        self.set_result(result)

class NetTestCommandKill(NetTestCommandGeneric):
    def run(self):
        bg_id = int(self._command["value"])
        pid = bg_processes.get_pid(bg_id)
        logging.debug("Killing background id \"%d\", pid \"%d\"" % (bg_id, pid))
        os.killpg(os.getpgid(pid), signal.SIGKILL)
        bg_processes.remove(bg_id)
        self.set_result({"passed": True})

def get_command_class(command):
    cmd_type = command["type"]
    if cmd_type == "exec":
        return NetTestCommandExec(command)
    elif cmd_type == "test":
        return NetTestCommandTest(command)
    elif cmd_type == "wait":
        return NetTestCommandWait(command)
    elif cmd_type == "intr":
        return NetTestCommandIntr(command)
    elif cmd_type == "kill":
        return NetTestCommandKill(command)
    elif cmd_type == "system_config":
        return NetTestCommandSystemConfig(command)
    else:
        logging.error("Unknown comamnd type \"%s\"" % cmd_type)
        raise Exception("Unknown command type \"%s\"" % cmd_type)

class NetTestCommand:
    def __init__(self, command):
        self._command_class = get_command_class(command)
        self._command = command

    def run(self):
        cmd_cls = self._command_class
        if "bg_id" in self._command:
            bg_id = self._command["bg_id"]
            read_pipe, write_pipe = os.pipe()
            pid = os.fork()
            if pid:
                os.close(write_pipe)
                logging.debug("Running in background with"
                              " id \"%d\", pid \"%d\"" % (bg_id, pid))
                bg_processes.add(bg_id, pid, read_pipe)
                return {"passed": True}
            os.close(read_pipe)
            os.setpgrp()
            cmd_cls.set_handle_intr()
            try:
                cmd_cls.run()
                result = cmd_cls.get_result()
            except KeyboardInterrupt:
                result = cmd_cls.get_result()
            except:
                type, value, tb = sys.exc_info()
                result = {"Exception": ''.join(traceback.format_exception(type, value, tb))}
            tmp = pickle.dumps(result)
            os.write(write_pipe, tmp)
            os.close(write_pipe)
            os._exit(0)
        else:
            cmd_cls.run()
            return cmd_cls.get_result()
