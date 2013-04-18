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
import multiprocessing
from lnst.Common.ExecCmd import exec_cmd, ExecCmdFail
from lnst.Common.ConnectionHandler import recv_data, send_data

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


class NetTestCommand:
    def __init__(self, command_context, command, resource_table, log_ctl):
        self._cmd_cls = get_command_class(command_context, command,
                                                resource_table)
        self._command_context = command_context
        self._command = command

        self._process = None
        self._id = None
        self._read_pipe = None
        self._write_pipe = None
        self._connection_pipe = None
        self._killed = False
        self._finished = False
        self._result = None
        self._log_ctl = log_ctl

        if "bg_id" not in self._command:
            self._id = None
        else:
            self._id = self._command["bg_id"]

    def get_id(self):
        return self._id

    def forked(self):
        return self._process != None

    def finished(self):
        return self._finished

    def run(self):
        if isinstance(self._cmd_cls, NetTestCommandControl):
            return self._cmd_cls.run()

        self._read_pipe, self._write_pipe = multiprocessing.Pipe()
        self._process = multiprocessing.Process(target=self._run)

        self._process.daemon = False
        self._process.start()
        self._pid = self._process.pid

        self._connection_pipe = self._read_pipe

        if not self._id:
            logging.debug("Running command with"
                          " pid \"%d\"" % (self._pid))
            return None
        else:
            logging.debug("Running in background with"
                          " bg_id \"%s\" pid \"%d\"" % (self._id, self._pid))
            return {"passed": True}

    def _run(self):
        os.setpgrp()
        self._cmd_cls.set_handle_intr()

        self._connection_pipe = self._write_pipe

        self._log_ctl.disable_logging()
        self._log_ctl.set_connection(self._connection_pipe)

        result = {}
        try:
            self._cmd_cls.run()
            res_data = self._cmd_cls.get_result()
            result["type"] = "result"
            result["cmd_id"] = self._id
            result["result"] = res_data
        except KeyboardInterrupt:
            res_data = self._cmd_cls.get_result()
            result["type"] = "result"
            result["cmd_id"] = self._id
            result["result"] = res_data
        except:
            type, value, tb = sys.exc_info()
            result = {"type": "exception",
                    "cmd_id": self._id,
                    "Exception": ''.join(traceback.format_exception(type,
                                                                    value, tb))}
        send_data(self._write_pipe, result)
        self._write_pipe.close()

    def join(self):
        self._process.join()

    def wait_for(self):
        logging.debug("Waiting for background command with id \"%s\", pid \"%d\"" % (self._id, self._pid))
        self._finished = True

    def interrupt(self):
        self._finished = True
        if os.path.exists("/proc/%d" % self._pid):
            logging.debug("Interrupting background command with id \"%s\", pid \"%d\"" % (self._id, self._pid))
            os.killpg(os.getpgid(self._pid), signal.SIGINT)

    def kill(self):
        if os.path.exists("/proc/%d" % self._pid):
            logging.debug("Killing background command with id \"%s\", pid \"%d\"" % (self._id, self._pid))
            self._killed = True
            os.killpg(os.getpgid(self._pid), signal.SIGKILL)
            self._process.join()

    def get_result(self):
        if self._killed:
            result = {}
            result["type"] = "result"
            result["passed"] = True
        else:
            result = self._result

        return result

    def set_result(self, result):
        self._result = result

    def get_connection_pipe(self):
        return self._connection_pipe

    def get_type(self):
        return self._command["type"]

class NetTestCommandContext:
    def __init__(self):
        self._dict = {}

    def add_cmd(self, cmd):
        self._dict[cmd.get_id()] = cmd

    def del_cmd(self, cmd):
        del self._dict[cmd.get_id()]

    def get_cmd(self, id):
        return self._dict[id]

    def _kill_all_cmds(self):
        for id in self._dict:
            self._dict[id].kill()

    def cleanup(self):
        self._kill_all_cmds()
        self._dict = {}

    def get_read_pipes(self):
        pipes = {}
        for key in self._dict:
            pipe = self._dict[key].get_connection_pipe()
            if pipe != None:
                pipes[key] = pipe
        return pipes

def NetTestCommandTest(command, resource_table):
    test_name = command["value"]
    if not test_name in resource_table["module"]:
        msg = "Test module '%s' not found" % test_name

    module_path = resource_table["module"][test_name]
    module_name = "Test%s" % test_name

    module = imp.load_source(module_name, module_path)
    test_class = getattr(module, module_name)
    return test_class(command)

class NetTestCommandGeneric:
    def __init__(self, command):
        self._command = command
        self._result = None
        self._resource_table = None

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

    def set_resource_table(self, res_table):
        self._resource_table = res_table

    def exec_cmd(self, cmd, *args, **kwargs):
        return exec_cmd(cmd, *args, **kwargs)

    def exec_from(self, tools_name, cmd, *args, **kwargs):
        if not tools_name in self._resource_table["tools"]:
            msg = "Tools '%s' not found" % tools_name
            raise CommandException(msg)

        tools_path = self._resource_table["tools"][tools_name]
        return exec_cmd("cd \"%s\" && %s" % (tools_path, cmd), *args, **kwargs)

class NetTestCommandExec(NetTestCommandGeneric):
    def run(self):
        try:
            if "from" in self._command:
                self.exec_from(self._command["from"], self._command["value"])
            else:
                self.exec_cmd(self._command["value"])
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
        bg_cmd = self._command_context.get_cmd(bg_id)
        bg_cmd.wait_for()
        result = bg_cmd.get_result()
        if result != None:
            bg_cmd.join()
            self._command_context.del_cmd(bg_cmd)
        return result

class NetTestCommandIntr(NetTestCommandControl):
    def run(self):
        bg_id = self._command["value"]
        bg_cmd = self._command_context.get_cmd(bg_id)
        bg_cmd.interrupt()
        result = bg_cmd.get_result()
        if result != None:
            bg_cmd.join()
            self._command_context.del_cmd(bg_cmd)
        return result

class NetTestCommandKill(NetTestCommandControl):
    def run(self):
        bg_id = self._command["value"]
        bg_cmd = self._command_context.get_cmd(bg_id)
        bg_cmd.kill()
        result = bg_cmd.get_result()
        if result != None:
            bg_cmd.join()
            self._command_context.del_cmd(bg_cmd)
        return result

def get_command_class(command_context, command, resource_table):
    cmd_type = command["type"]
    if cmd_type == "exec":
        cmd_cls = NetTestCommandExec(command)
    elif cmd_type == "test":
        cmd_cls = NetTestCommandTest(command, resource_table)
    elif cmd_type == "wait":
        cmd_cls = NetTestCommandWait(command_context, command)
    elif cmd_type == "intr":
        cmd_cls = NetTestCommandIntr(command_context, command)
    elif cmd_type == "kill":
        cmd_cls = NetTestCommandKill(command_context, command)
    elif cmd_type == "system_config":
        cmd_cls = NetTestCommandSystemConfig(command)
    else:
        logging.error("Unknown comamnd type \"%s\"" % cmd_type)
        raise Exception("Unknown command type \"%s\"" % cmd_type)

    cmd_cls.set_resource_table(resource_table)
    return cmd_cls
