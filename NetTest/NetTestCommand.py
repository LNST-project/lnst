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
        out += ", bg_id (%s)" % command["bg_id"]
    if "desc" in command:
        out += ", desc (%s)" % command["desc"]
    return out

class CommandException(Exception):
    """Base class for client errors."""
    def __init__(self, command):
        self.command = command

    def __str__(self):
        return "CommandException: " + str(self.command)

class BgCommandException(Exception):
    """Base class for background command errors."""
    def __init__(self, str):
        self._str = str

    def __str__(self):
        return "BgCommandError: " + self._str

class BgCommand:
    def __init__(self, bg_id, cmd_cls):
        self._bg_id = bg_id
        self._cmd_cls = cmd_cls
        self._pid = None
        self._read_pipe = None

    def get_bg_id(self):
        return self._bg_id

    def run(self):
        read_pipe, write_pipe = os.pipe()
        self._pid = os.fork()
        if self._pid:
            os.close(write_pipe)
            logging.debug("Running in background with"
                          " id \"%s\", pid \"%d\"" % (self._bg_id, self._pid))
            self._read_pipe = read_pipe
            return {"passed": True}
        os.close(read_pipe)
        os.setpgrp()
        self._cmd_cls.set_handle_intr()
        try:
            self._cmd_cls.run()
            result = self._cmd_cls.get_result()
        except KeyboardInterrupt:
            result = self._cmd_cls.get_result()
        except:
            type, value, tb = sys.exc_info()
            result = {"Exception": ''.join(traceback.format_exception(type, value, tb))}
        tmp = pickle.dumps(result)
        os.write(write_pipe, tmp)
        os.close(write_pipe)
        os._exit(0)

    def wait_for(self):
        logging.debug("Waiting for background command with id \"%s\", pid \"%d\"" % (self._bg_id, self._pid))
        os.waitpid(self._pid, 0)

    def interrupt(self):
        logging.debug("Interrupting background command with id \"%s\", pid \"%d\"" % (self._bg_id, self._pid))
        os.killpg(os.getpgid(self._pid), signal.SIGINT)
        os.waitpid(self._pid, 0)

    def kill(self):
        logging.debug("Killing background command with id \"%s\", pid \"%d\"" % (self._bg_id, self._pid))
        os.killpg(os.getpgid(self._pid), signal.SIGKILL)

    def get_result(self):
        tmp = os.read(self._read_pipe, 4096*10)
        result = pickle.loads(tmp)
        if "Exception" in result:
            raise BgCommandException(result["Exception"])
        os.close(self._read_pipe)
        return result

class NetTestCommandContext:
    def __init__(self):
        self._dict = {}

    def add_bg_cmd(self, bg_cmd):
        self._dict[bg_cmd.get_bg_id()] = bg_cmd

    def del_bg_cmd(self, bg_cmd):
        del self._dict[bg_cmd.get_bg_id()]

    def get_bg_cmd(self, bg_id):
        return self._dict[bg_id]

    def _kill_all_bg_cmds(self):
        for bg_id in self._dict:
            self._dict[bg_id].kill()

    def cleanup(self):
        self._kill_all_bg_cmds()
        self._dict = {}

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

class NetTestCommandControl(NetTestCommandGeneric):
    def __init__(self, command_context, command):
        self._command_context = command_context
        NetTestCommandGeneric.__init__(self, command)

class NetTestCommandWait(NetTestCommandControl):
    def run(self):
        bg_id = self._command["value"]
        bg_cmd = self._command_context.get_bg_cmd(bg_id)
        bg_cmd.wait_for()
        result = bg_cmd.get_result()
        self._command_context.del_bg_cmd(bg_cmd)
        self.set_result(result)

class NetTestCommandIntr(NetTestCommandControl):
    def run(self):
        bg_id = self._command["value"]
        bg_cmd = self._command_context.get_bg_cmd(bg_id)
        bg_cmd.interrupt()
        result = bg_cmd.get_result()
        self._command_context.del_bg_cmd(bg_cmd)
        self.set_result(result)

class NetTestCommandKill(NetTestCommandControl):
    def run(self):
        bg_id = self._command["value"]
        bg_cmd = self._command_context.get_bg_cmd(bg_id)
        bg_cmd.kill()
        self._command_context.del_bg_cmd(bg_cmd)
        self.set_result({"passed": True})

def get_command_class(command_context, command):
    cmd_type = command["type"]
    if cmd_type == "exec":
        return NetTestCommandExec(command)
    elif cmd_type == "test":
        return NetTestCommandTest(command)
    elif cmd_type == "wait":
        return NetTestCommandWait(command_context, command)
    elif cmd_type == "intr":
        return NetTestCommandIntr(command_context, command)
    elif cmd_type == "kill":
        return NetTestCommandKill(command_context, command)
    elif cmd_type == "system_config":
        return NetTestCommandSystemConfig(command)
    else:
        logging.error("Unknown comamnd type \"%s\"" % cmd_type)
        raise Exception("Unknown command type \"%s\"" % cmd_type)

class NetTestCommand:
    def __init__(self, command_context, command):
        self._command_class = get_command_class(command_context, command)
        self._command_context = command_context
        self._command = command

    def run(self):
        cmd_cls = self._command_class
        if "bg_id" in self._command:
            bg_id = self._command["bg_id"]
            bg_cmd = BgCommand(bg_id, cmd_cls)
            self._command_context.add_bg_cmd(bg_cmd)
            return bg_cmd.run()
        else:
            cmd_cls.run()
            return cmd_cls.get_result()
