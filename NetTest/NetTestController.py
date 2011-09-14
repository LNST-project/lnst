"""
This module defines NetTestController class which does the controlling
part of network testing.

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import logging
import socket
from pprint import pprint, pformat
from Common.XmlRpc import ServerProxy
from NetTestParse import NetTestParse
from Common.SlaveUtils import prepare_client_session
from Common.Utils import get_corespond_local_ip
from NetTestSlave import DefaultRPCPort
from NetTestCommand import NetTestCommand, str_command
from Common.LoggingServer import LoggingServer

class NetTestController:
    def __init__(self, recipe_path, remoteexec=False, cleanup=False,
                 res_serializer=None):
        ntparse = NetTestParse(recipe_path)
        ntparse.parse_recipe()
        self._recipe = ntparse.get_recipe()
        self._ntparse = ntparse
        self._remoteexec = remoteexec
        self._docleanup = cleanup
        self._res_serializer = res_serializer

    def _get_machineinfo(self, machine_id):
        return self._recipe["machines"][machine_id]["info"]

    def _get_machinerpc(self, machine_id):
        return self._get_machineinfo(machine_id)["rpc"]

    def _session_die(self, session, status):
        logging.error("Session started with cmd %s die with status %s." % (session.command, status))
        raise Exception("Session Die.")

    def _prepare_slaves(self):
        for machine_id in self._recipe["machines"]:
            info = self._get_machineinfo(machine_id)
            hostname = info["hostname"]
            logging.info("Remote app exec on machine %s" % hostname)
            port = "22"
            login = "root"
            if "rootpass" in info:
                passwd = info["rootpass"]
            else:
                passwd = None
            session = prepare_client_session(hostname, port, login, passwd,
                                             "nettestslave.py")
            session.add_kill_handler(self._session_die)
            info["session"] = session

    def _cleanup_slaves(self):
        for machine_id in self._recipe["machines"]:
            info = self._get_machineinfo(machine_id)
            if "session" in info:
                info["session"].kill()
                info["session"].wait()

    def _rpc_connect(self):
        for machine_id in self._recipe["machines"]:
            info = self._get_machineinfo(machine_id)
            hostname = info["hostname"]
            logging.info("Connecting to RPC on machine \"%s\"" % hostname)
            if "rpcport" in info:
                port = info["rpcport"]
            else:
                port = DefaultRPCPort
            url = "http://%s:%d" % (hostname, port)
            rpc = ServerProxy(url, allow_none = True)
            if rpc.hello() != "hello":
                logging.error("Handshake error with machine id %d" % machine_id)
                raise Exception("Hanshake error")
            if self._docleanup:
                rpc.machine_cleanup()
            info["rpc"] = rpc

    def _logging_connect(self):
        for machine_id in self._recipe["machines"]:
            info = self._get_machineinfo(machine_id)
            logging.info("Setting logging server on machine \"%s\"" % info["hostname"])
            rpc = self._get_machinerpc(machine_id)
            ip = get_corespond_local_ip(info["hostname"])
            rpc.set_logging(ip, LoggingServer.DEFAULT_PORT)

    def _netconfigs_set(self):
        machines = self._recipe["machines"]
        for machine_id in machines:
            machine = machines[machine_id]
            logging.info("Setting netconfigs on machine \"%s\"" % machine["info"]["hostname"])
            rpc = self._get_machinerpc(machine_id)
            rpc.netconfig_set(machine["netmachineconfig_xml"],
                              machine["netconfig_xml"])
            '''
            Finally get processed netconfig from slave back to us.
            Will be handy later on.
            '''
            machine["netconfig"] = dict(rpc.netconfig_dump())
            del machine["netmachineconfig_xml"]
            del machine["netconfig_xml"]

    def _netconfigs_clear(self):
        machines = self._recipe["machines"]
        for machine_id in machines:
            machine = machines[machine_id]
            logging.info("Clearing netconfigs on machine \"%s\"" % machine["info"]["hostname"])
            rpc = self._get_machinerpc(machine_id)
            rpc.netconfig_clear()

    def _prepare(self):
        if self._remoteexec:
            self._prepare_slaves()
        self._rpc_connect()
        self._logging_connect()
        self._netconfigs_set()

        '''
        Now as we have all netconfigs processed by slaves back, it's time to
        parse recipe command sequence
        '''
        self._ntparse.parse_recipe_command_sequence()
        self._recipe = self._ntparse.get_recipe()

    def _cleanup(self):
        self._netconfigs_clear()
        if self._remoteexec:
            self._cleanup_slaves()

    def _run_command(self, command):
        cmd_type = command["type"]
        machine_id = command["machine_id"]

        try:
            desc = command["desc"]
            logging.info("Cmd description: %s" % desc)
        except KeyError:
            pass

        if machine_id == 0:
            cmd_res = NetTestCommand(command).run()
        else:
            info = self._get_machineinfo(machine_id)
            hostname = info["hostname"]
            rpc = self._get_machinerpc(machine_id)
            if "timeout" in command:
                timeout = command["timeout"]
                logging.debug("Setting socket timeout to \"%d\"" % timeout)
                socket.setdefaulttimeout(timeout)
            try:
                cmd_res = rpc.run_command(command)
            except socket.timeout:
                logging.error("Slave reply timed out")
                raise Exception("Slave reply timed out")
            if "timeout" in command:
                logging.debug("Setting socket timeout to default value")
                socket.setdefaulttimeout(None)
        return cmd_res

    def _run_command_sequence(self):
        sequence = self._recipe["sequence"]
        for command in sequence:
            logging.info("Executing command: [%s]" % str_command(command))
            cmd_res = self._run_command(command)
            if self._res_serializer:
                self._res_serializer.add_cmd_result(command, cmd_res)
            logging.debug("Result: %s" % str(cmd_res))
            if "res_data" in cmd_res:
                res_data = pformat(cmd_res["res_data"])
                logging.info("Result data: %s" % (res_data))
            if not cmd_res["passed"]:
                logging.error("Command failed - command: [%s], "
                              "Error message: \"%s\""
                                % (str_command(command), cmd_res["err_msg"]))
                return False
        return True

    def dump_recipe(self):
        pprint(self._recipe)
        return True

    def all_dump_recipe(self):
        self._prepare()
        pprint(self._recipe)
        return True

    def config_only_recipe(self):
        self._prepare()
        return True

    def run_recipe(self):
        self._prepare()
        res = self._run_command_sequence()
        self._cleanup()
        return res

    def eval_expression_recipe(self, expr):
        self._prepare()
        value = eval("self._recipe%s" % expr)
        print "Evaluated expression \"%s\": \"%s\"" % (expr, value)
        return True
