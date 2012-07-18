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
import os
from Common.Logs import Logs
from Common.SshUtils import scp_from_remote
from pprint import pprint, pformat
from Common.XmlRpc import ServerProxy
from NetTest.NetTestParse import NetTestParse
from Common.SlaveUtils import prepare_client_session
from Common.Utils import get_corespond_local_ip
from NetTest.NetTestSlave import DefaultRPCPort
from NetTest.NetTestCommand import NetTestCommand, str_command
from Common.LoggingServer import LoggingServer

def ignore_event(**kwarg):
    pass

class NetTestController:
    def __init__(self, recipe_path, remoteexec=False, cleanup=False,
                 res_serializer=None):
        self._remoteexec = remoteexec
        self._docleanup = cleanup
        self._res_serializer = res_serializer
        self._remote_capture_files = {}

        self._recipe = {}
        definitions = {"recipe": self._recipe}

        ntparse = NetTestParse(recipe_path)
        ntparse.set_recipe(self._recipe)
        ntparse.set_definitions(definitions)

        ntparse.register_event_handler("netdevice_ready", ignore_event)
        ntparse.register_event_handler("machine_info_ready",
                                        self._prepare_slave)
        ntparse.register_event_handler("interface_config_ready",
                                        self._prepare_interface)

        self._ntparse = ntparse

    def _get_machineinfo(self, machine_id):
        try:
            info = self._recipe["machines"][machine_id]["info"]
        except KeyError:
            msg = "Machine info is required, but not yet available"
            raise Exception(msg)

        return info

    def _get_machinerpc(self, machine_id):
        try:
            rpc = self._get_machineinfo(machine_id)["rpc"]
        except KeyError:
            msg = "XMLRPC connection required, but not yet available"
            raise Exception(msg)

        return rpc

    @staticmethod
    def _session_die(session, status):
        logging.error("Session started with cmd %s die with status %s.",
                                        session.command, status)
        raise Exception("Session Die.")

    def _prepare_interface(self, machine_id, netdev_config_id):
        rpc = self._get_machinerpc(machine_id)
        info = self._get_machineinfo(machine_id)
        logging.info("Configuring interface #%d on %s", netdev_config_id,
                                                        info["hostname"])

        self._configure_interface(machine_id, netdev_config_id)

        if_info = rpc.get_interface_info(netdev_config_id)
        machine = self._recipe["machines"][machine_id]
        if "name" in if_info:
            machine["netconfig"][netdev_config_id]["name"] = if_info["name"]

        info["configured_interfaces"].append(netdev_config_id)

    def _configure_interface(self, machine_id, netdev_config_id):
        rpc = self._get_machinerpc(machine_id)
        netconfig = self._recipe["machines"][machine_id]["netconfig"]
        dev_config = netconfig[netdev_config_id]

        rpc.configure_interface(netdev_config_id, dev_config)

    def _deconfigure_interface(self, machine_id, netdev_config_id):
        rpc = self._get_machinerpc(machine_id)
        rpc.deconfigure_interface(netdev_config_id)

    def _prepare_slave(self, machine_id):
        logging.info("Preparing machine #%d", machine_id)
        info = self._get_machineinfo(machine_id)

        if self._remoteexec and not "session" in info:
            self._init_slave_session(machine_id)

        if not "rpc" in info:
            self._init_slave_rpc(machine_id)
            self._init_slave_logging(machine_id)

            info["configured_interfaces"] = []

    def _init_slave_session(self, machine_id):
        info = self._get_machineinfo(machine_id)
        hostname = info["hostname"]
        if "rootpass" in info:
            passwd = info["rootpass"]
        else:
            passwd = None
        logging.info("Remote app exec on machine %s", hostname)

        port = "22"
        login = "root"
        session = prepare_client_session(hostname, port, login, passwd,
                                         "nettestslave.py")
        session.add_kill_handler(self._session_die)
        info["session"] = session

    def _init_slave_rpc(self, machine_id):
        info = self._get_machineinfo(machine_id)
        hostname = info["hostname"]
        if "rpcport" in info:
            port = info["rpcport"]
        else:
            port = DefaultRPCPort
        logging.info("Connecting to RPC on machine %s", hostname)

        url = "http://%s:%d" % (hostname, port)
        rpc = ServerProxy(url, allow_none = True)
        if rpc.hello() != "hello":
            logging.error("Handshake error with machine %s", hostname)
            raise Exception("Hanshake error")

        if self._docleanup:
            rpc.machine_cleanup()

        info["rpc"] = rpc

    def _init_slave_logging(self, machine_id):
        info = self._get_machineinfo(machine_id)
        hostname = info["hostname"]
        logging.info("Setting logging server on machine %s", hostname)
        rpc = self._get_machinerpc(machine_id)
        ip_addr = get_corespond_local_ip(hostname)
        rpc.set_logging(ip_addr, LoggingServer.DEFAULT_PORT)

    def _cleanup_slave(self, machine_id):
        info = self._get_machineinfo(machine_id)

        if self._docleanup:
            rpc = self._get_machinerpc(machine_id)
            for if_id in reversed(info["configured_interfaces"]):
                rpc.deconfigure_interface(if_id)

        if self._remoteexec and "session" in info:
            info["session"].kill()
            info["session"].wait()

    def _prepare(self):
        # All the perparations are made within the recipe parsing
        # This is achieved by handling parser events (by registering
        self._ntparse.parse_recipe()

    def _cleanup(self):
        for machine_id in self._recipe["machines"]:
            self._cleanup_slave(machine_id)

    def _run_command(self, command):
        machine_id = command["machine_id"]
        try:
            desc = command["desc"]
            logging.info("Cmd description: %s", desc)
        except KeyError:
            pass

        if machine_id == 0:
            cmd_res = NetTestCommand(command).run()
        else:
            rpc = self._get_machinerpc(machine_id)
            if "timeout" in command:
                timeout = command["timeout"]
                logging.debug("Setting socket timeout to \"%d\"", timeout)
                socket.setdefaulttimeout(timeout)
            try:
                cmd_res = rpc.run_command(command)
            except socket.timeout:
                logging.error("Slave reply timed out")
                raise Exception("Slave reply timed out")
            if "timeout" in command:
                logging.debug("Setting socket timeout to default value")
                socket.setdefaulttimeout(None)

        if command["type"] == "system_config":
            if cmd_res["passed"]:
                self._update_system_config(machine_id, cmd_res["res_data"],
                                                command["persistent"])
            else:
                err = "Error occured while setting system configuration (%s)" \
                                                    % cmd_res["err_msg"]
                logging.error(err)

        return cmd_res

    def _run_command_sequence(self, sequence):
        seq_passed = True
        for command in sequence:
            logging.info("Executing command: [%s]", str_command(command))
            cmd_res = self._run_command(command)
            if self._res_serializer:
                self._res_serializer.add_cmd_result(command, cmd_res)
            logging.debug("Result: %s", str(cmd_res))
            if "res_data" in cmd_res:
                res_data = pformat(cmd_res["res_data"])
                logging.info("Result data: %s", (res_data))
            if not cmd_res["passed"]:
                logging.error("Command failed - command: [%s], "
                              "Error message: \"%s\"",
                              str_command(command), cmd_res["err_msg"])
                seq_passed = False
        return seq_passed

    def dump_recipe(self):
        self._prepare()
        pprint(self._recipe)
        self._cleanup()
        return True

    def config_only_recipe(self):
        self._prepare()
        self._cleanup()
        return True

    def run_recipe(self, packet_capture=False):
        self._prepare()

        if packet_capture:
            self._start_packet_capture()

        err = None
        try:
            res = self._run_recipe()
        except Exception, exc:
            err = exc

        if packet_capture:
            self._stop_packet_capture()
            self._gather_capture_files()

        self._cleanup()

        if not err:
            return res
        else:
            raise err

    def _run_recipe(self):
        for sequence in self._recipe["sequences"]:
            res = self._run_command_sequence(sequence)

            for machine_id in self._recipe["machines"]:
                self._restore_system_config(machine_id)

            # stop when sequence fails
            if not res:
                break

        return res

    def _start_packet_capture(self):
        logging.info("Starting packet capture")
        for machine_id in self._recipe["machines"]:
            rpc = self._get_machinerpc(machine_id)
            capture_files = rpc.start_packet_capture("")
            self._remote_capture_files[machine_id] = capture_files

    def _stop_packet_capture(self):
        logging.info("Stopping packet capture")
        for machine_id in self._recipe["machines"]:
            rpc = self._get_machinerpc(machine_id)
            rpc.stop_packet_capture()

    def _gather_capture_files(self):
        logging_root = Logs.get_logging_root_path()
        logging_root = os.path.abspath(logging_root)
        logging.info("Retrieving capture files from slaves")
        for machine_id in self._recipe["machines"]:
            hostname = self._recipe["machines"][machine_id]['info']['hostname']
            rootpass = self._recipe["machines"][machine_id]['info']['rootpass']

            slave_logging_dir = os.path.join(logging_root, hostname)
            try:
                os.mkdir(slave_logging_dir)
            except OSError, err:
                if err.errno != 17:
                    raise

            capture_files = self._remote_capture_files[machine_id]
            for remote_path in capture_files:
                filename = os.path.basename(remote_path)
                local_path = os.path.join(slave_logging_dir, filename)
                scp_from_remote(hostname, "22", "root", rootpass,
                                    remote_path, local_path)

    def _update_system_config(self, machine_id, res_data, persistent=False):
        info = self._get_machineinfo(machine_id)
        system_config = info["system_config"]
        for option, values in res_data.iteritems():
            if persistent:
                if option in system_config:
                    del system_config[option]
            else:
                if not option in system_config:
                    initial_val = {"initial_val": values["previous_val"]}
                    system_config[option] = initial_val
                system_config[option]["current_val"] = values["current_val"]


    def _restore_system_config(self, machine_id):
        info = self._get_machineinfo(machine_id)
        system_config = info["system_config"]

        if len(system_config) > 0:
            command = {}
            command["machine_id"] = machine_id
            command["type"] = "system_config"
            command["value"] = ""
            command["options"] = {}
            command["persistent"] = True
            for option, values in system_config.iteritems():
                command["options"][option] = [{"value": values["initial_val"]}]

            self._run_command_sequence([command])
            info["system_config"] = {}
