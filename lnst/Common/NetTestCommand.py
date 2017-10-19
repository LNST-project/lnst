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
import multiprocessing
import re
from time import time
from lnst.Common.ExecCmd import exec_cmd, ExecCmdFail
from lnst.Common.ConnectionHandler import send_data
from lnst.Common.Logs import log_exc_traceback

DEFAULT_TIMEOUT = 60

def str_command(command):
    attrs = ["type(%s)" % command["type"]]
    if command["type"] == "test":
        attrs.append("module(%s)" % command["module"])
        attrs.append("host(%s)" % command["host"])

        if "bg_id" in command:
            attrs.append("bg_id(%s)" % command["bg_id"])
        if "timeout" in command:
            attrs.append("timeout(%s)" % command["timeout"])
    elif command["type"] == "exec":
        attrs.append("command(%s)" % command["command"])
        attrs.append("host(%s)" % command["host"])

        if "from" in command:
            attrs.append("from(%s)" % command["from"])
        if "bg_id" in command:
            attrs.append("bg_id(%s)" % command["bg_id"])
        if "timeout" in command:
            attrs.append("timeout(%s)" % command["timeout"])
    elif command["type"] in ["wait", "intr", "kill"]:
        attrs.append("host(%s)" % command["host"])
        attrs.append("bg_id(%s)" % command["proc_id"])
    elif command["type"] == "config":
        attrs.append("host(%s)" % command["host"])

        if "option" in command:
            attrs.append("option(%s)" % command["option"])
        if "value" in command:
            attrs.append("value(%s)" % command["value"])
    elif command["type"] == "ctl_wait":
        attrs.append("seconds(%s)" % command["seconds"])
    else:
        raise RuntimeError("Unknown command type '%s'" % command["type"])

    if "netns" in command:
        attrs.append("netns(%s)" % command["netns"])

    return ", ".join(attrs)

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
        self._control_cmd= None
        self._result = None
        self._log_ctl = log_ctl
        self._start_time = None
        self._result_sent = False

        if "bg_id" not in self._command:
            self._id = None
        else:
            self._id = self._command["bg_id"]

    def get_id(self):
        return self._id

    def forked(self):
        return self._process != None

    def set_result_sent(self, value=True):
        self._result_sent = value

    def get_result_sent(self):
        return self._result_sent

    def finished(self):
        return self._finished

    def run(self):
        self._start_time = time()
        if isinstance(self._cmd_cls, NetTestCommandControl) or \
           isinstance(self._cmd_cls, NetTestCommandConfig):
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
            return {"passed": True,
                    "res_header": self._cmd_cls._format_cmd_res_header(),
                    "msg": "Running in background."}

    def _sig_ign(self, signum, frame):
        pass

    def _run(self):
        os.setpgrp()
        signal.signal(signal.SIGHUP, self._sig_ign)
        signal.signal(signal.SIGINT, self._sig_ign)
        signal.signal(signal.SIGTERM, self._sig_ign)

        self._connection_pipe = self._write_pipe

        self._log_ctl.disable_logging()
        self._log_ctl.set_connection(self._connection_pipe)

        result = {}
        try:
            self._cmd_cls.run()
        except (KeyboardInterrupt, SystemExit):
            pass
        except:
            log_exc_traceback()
            type, value, tb = sys.exc_info()
            data = {"Exception": "%s" % value}
            self._cmd_cls.set_fail(data)
        finally:
            res_data = self._cmd_cls.get_result()
            result["type"] = "result"
            result["cmd_id"] = self._id
            result["result"] = res_data

        send_data(self._write_pipe, result)
        self._write_pipe.close()

    def join(self):
        self._process.join()

    def wait_for(self, cmd):
        logging.debug("Waiting for background command with id \"%s\", pid \"%d\"" % (self._id, self._pid))
        self._finished = True
        self._control_cmd = cmd

    def interrupt(self, cmd):
        self._finished = True
        if os.path.exists("/proc/%d" % self._pid):
            logging.debug("Interrupting background command with id \"%s\", pid \"%d\"" % (self._id, self._pid))
            os.killpg(os.getpgid(self._pid), signal.SIGINT)
        self._control_cmd = cmd

    def kill(self, cmd):
        if os.path.exists("/proc/%d" % self._pid):
            if self._id:
                logging.debug("Killing background command with id \"%s\", pid \"%d\"" % (self._id, self._pid))
            else:
                logging.debug("Killing command with  pid \"%d\"" % self._pid)
            self._killed = True
            os.killpg(os.getpgid(self._pid), signal.SIGKILL)
            self._process.join()
            self._control_cmd = cmd

    def get_result(self):
        if self._killed:
            self._cmd_cls.set_pass()
            result = self._cmd_cls.get_result()
            result["passed"] = True
            result["msg"] = "Command killed."
            result["killed"] = True
            self._result = result

        return self._result

    def set_result(self, result):
        if self._control_cmd != None:
            result["res_header"] = self._control_cmd._format_cmd_res_header()
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
        if id in self._dict:
            return self._dict[id]
        else:
            return None

    def _kill_all_cmds(self):
        for id in self._dict:
            self._dict[id].kill(None)

    def cleanup(self):
        logging.debug("Cleaning up leftover processes.")
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
    test_name = command["module"]
    if not test_name in resource_table["module"]:
        msg = "Test module '%s' not found" % test_name
        raise Exception(msg)

    module_path = resource_table["module"][test_name]
    module_name = test_name

    module = imp.load_source(module_name, module_path)
    test_class = getattr(module, module_name)
    return test_class(command)

class NetTestCommandGeneric(object):
    def __init__(self, command):
        self._command = command
        self._result = None
        self._resource_table = None

    def run(self):
        pass

    def get_result(self):
        if not self._result:
            '''
            In case result is not set yet, it most likely means that
            command was killed. So set pass in this case
            '''
            self.set_pass()
        return self._result

    def set_fail(self, res_data=None):
        res = False
        msg = ""
        if "expect" in self._command and self._command["expect"] == False:
            res = True
            msg = "Command failed, as was specified in the recipe."
        result = {"passed": res,
                  "res_data": res_data,
                  "msg": msg,
                  "report": self.format_res_data(res_data),
                  "res_header": self._format_cmd_res_header()}
        self._result = result
        return result

    def set_pass(self, res_data=None):
        res = True
        msg = ""
        if "expect" in self._command and self._command["expect"] == False:
            res = False
            msg = "Command expected to fail, but passed!"
        result = {"passed": res,
                  "res_data": res_data,
                  "msg": msg,
                  "report": self.format_res_data(res_data),
                  "res_header": self._format_cmd_res_header()}
        self._result = result
        return result

    def format_res_data(self, res_data, level=0):
        self._check_res_data(res_data)
        formatted_data = ""
        if res_data:
            max_key_len = 0
            for key in res_data.keys():
                if len(key) > max_key_len:
                    max_key_len = len(key)
            for key, value in res_data.iteritems():
                if type(value) == dict:
                    formatted_data += level*4*" " + str(key) + ":\n"
                    formatted_data += self.format_res_data(value, level+1)
                elif type(value) == list:
                    formatted_data += level*4*" " + str(key) + ":\n"
                    for i in range(0, len(value)):
                        formatted_data += (level+1)*4*" " +\
                                          "item %d:" % (i+1) + "\n"
                        formatted_data += self.format_res_data(value[i],
                                                               level+2)
                else:
                    formatted_data += level*4*" " + str(key) + ":" + \
                                      (max_key_len-len(key))*" " + \
                                      "\t" + str(value) + "\n"

        return formatted_data

    def _check_res_data(self, res_data):
        name_start_char = u":A-Z_a-z\xC0-\xD6\xD8-\xF6\xF8-\u02FF"\
                          u"\u0370-\u037D\u037F-\u1FFF\u200C-\u200D"\
                          u"\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF"\
                          u"\uF900-\uFDCF\uFDF0-\uFFFD\U00010000-\U000EFFFF"
        name_char = name_start_char + u"\-\.0-9\xB7\u0300-\u036F\u203F-\u2040"
        name = u"[%s]([%s])*$" % (name_start_char, name_char)
        char_data = u"[^<&]*"
        if isinstance(res_data, dict):
            for key in res_data:
                if not re.match(name, key, re.UNICODE):
                    msg = "'%s' can't be used as an xml element name!" % key
                    raise CommandException(msg)
                else:
                    self._check_res_data(res_data[key])
        elif isinstance(res_data, list):
            for i in res_data:
                self._check_res_data(i)
        else:
            try:
                string = str(res_data)
            except:
                msg = "res_data can only contain dictionaries, lists or "\
                      "stringable objects!"
                raise CommandException(msg)
            if not re.match(char_data, string, re.UNICODE):
                msg = "'%s' can't be used as character data in xml!" % string
                raise CommandException(msg)

    def _format_cmd_res_header(self):
        if "netns" in self._command and self._command["netns"] != None:
            netns = "(%s) " % self._command["netns"]
        else:
            netns = ""

        return "%-9s" % (self._command["type"] + netns)

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
    def __init__(self, command):
        super(NetTestCommandExec, self).__init__(command)

    def run(self):
        try:
            if "from" in self._command:
                stdout, stderr = self.exec_from(self._command["from"],
                                                self._command["command"])
            else:
                json = True if "json" in self._command and self._command["json"] else False
                stdout, stderr = self.exec_cmd(self._command["command"], json=json)
            res_data = {"stdout": stdout, "stderr": stderr}
            self.set_pass(res_data)
        except ExecCmdFail as e:
            res_data = {"stdout": e.get_stdout(), "stderr": e.get_stderr()}
            if "bg_id" in self._command:
                logging.info("Command probably intentionally killed. Passing.")
                self.set_pass(res_data)
            else:
                self.set_fail(res_data)

    def format_res_data(self, res_data, level=0):
        return ""

    def _format_cmd_res_header(self):
        cmd_type = self._command["type"]
        cmd_val = self._command["command"]

        if "bg_id" in self._command:
            bg_id = "bg_id: %s " % self._command["bg_id"]
        else:
            bg_id = ""

        if "netns" in self._command and self._command["netns"] != None:
            netns = "(%s) " % self._command["netns"]
        else:
            netns = ""

        cmd = "%-9s%scmd: \"%s\"" %(cmd_type + netns, bg_id, cmd_val)
        return cmd

class NetTestCommandConfig(NetTestCommandGeneric):
    def _retrive_option(self, option):
        cmd_str = "cat %s" % option
        (stdout, stderr) = exec_cmd(cmd_str)
        return stdout.strip()

    def _set_option(self, option, value):
        cmd_str = "echo \"%s\" >%s" % (value, option)
        (stdout, stderr) = exec_cmd(cmd_str)

    def run(self):
        res_data = {"options": [], "persistent": False}

        for opt in self._command["options"]:
            option = opt["name"]
            value = opt["value"]
            option_abspath = os.path.abspath(option)
            if option_abspath[0:5] != "/sys/" and \
               option_abspath[0:6] != "/proc/":
                err = "Wrong config option %s. Only /proc or /sys paths are " \
                      "allowed." % option
                res_data["err_msg"] = err
                return self.set_fail(res_data)

            try:
                prev_val = self._retrive_option(option)
                self._set_option(option, value)
            except ExecCmdFail:
                err = "Unable to set %s config option!" % option
                res_data["err_msg"] = err
                return self.set_fail(res_data)

            if "persistent" in self._command:
                res_data["persistent"] = self._command["persistent"]

            res_data["options"].append({"name": option,
                                        "current_val": value,
                                        "previous_val": prev_val})

        self.set_pass(res_data)
        return self.get_result()

    def format_res_data(self, res_data, level=0):
        formatted_data = ""
        max_name_len = 0
        for option in res_data["options"]:
            if len(option["name"]) > max_name_len:
                max_name_len = len(option["name"])
        for option in res_data["options"]:
            vals = "previous: %s current: %s" % (option["previous_val"],
                                                 option["current_val"])
            formatted_data += 4*level*" " + option["name"] +  \
                              (max_name_len - len(option["name"]))*" " + \
                              "\t" + vals + "\n"
        return formatted_data

class NetTestCommandControl(NetTestCommandGeneric):
    def __init__(self, command_context, command):
        self._command_context = command_context
        NetTestCommandGeneric.__init__(self, command)

    def _format_cmd_res_header(self):
        cmd_type = self._command["type"]
        cmd_val = self._command["proc_id"]

        if "netns" in self._command and self._command["netns"] != None:
            netns = "(%s) " % self._command["netns"]
        else:
            netns = ""

        cmd = "%-9s id: %s" % (cmd_type + netns, cmd_val)
        return cmd

class NetTestCommandWait(NetTestCommandControl):
    def run(self):
        bg_id = self._command["proc_id"]
        bg_cmd = self._command_context.get_cmd(bg_id)
        bg_cmd.wait_for(self)
        result = bg_cmd.get_result()
        if result != None:
            bg_cmd.join()
            self._command_context.del_cmd(bg_cmd)
            result["res_header"] = self._format_cmd_res_header()
        return result

class NetTestCommandIntr(NetTestCommandControl):
    def run(self):
        bg_id = self._command["proc_id"]
        bg_cmd = self._command_context.get_cmd(bg_id)
        bg_cmd.interrupt(self)
        result = bg_cmd.get_result()
        if result != None:
            bg_cmd.join()
            self._command_context.del_cmd(bg_cmd)
            result["res_header"] = self._format_cmd_res_header()
        return result

class NetTestCommandKill(NetTestCommandControl):
    def run(self):
        bg_id = self._command["proc_id"]
        bg_cmd = self._command_context.get_cmd(bg_id)
        bg_cmd.kill(self)
        result = bg_cmd.get_result()
        if result != None:
            bg_cmd.join()
            self._command_context.del_cmd(bg_cmd)
            result["res_header"] = self._format_cmd_res_header()
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
    elif cmd_type == "config":
        cmd_cls = NetTestCommandConfig(command)
    else:
        logging.error("Unknown comamnd type \"%s\"" % cmd_type)
        raise Exception("Unknown command type \"%s\"" % cmd_type)

    cmd_cls.set_resource_table(resource_table)
    return cmd_cls
