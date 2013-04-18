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
import re
import pickle
import tempfile
from time import sleep
from xmlrpclib import Binary
from pprint import pprint, pformat
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.XmlRpc import ServerProxy, ServerException
from lnst.Common.NetUtils import MacPool
from lnst.Common.VirtUtils import VirtNetCtl, VirtDomainCtl, BridgeCtl
from lnst.Common.Utils import wait_for, md5sum, dir_md5sum, create_tar_archive
from lnst.Common.Utils import check_process_running
from lnst.Common.NetTestCommand import NetTestCommandContext, NetTestCommand
from lnst.Common.NetTestCommand import str_command, CommandException
from lnst.Controller.RecipeParse import RecipeParse
from lnst.Controller.SlavePool import SlavePool
from lnst.Controller.Machine import Machine, MachineError
from lnst.Common.ConnectionHandler import send_data, recv_data
from lnst.Common.ConnectionHandler import ConnectionHandler

class NetTestError(Exception):
    pass

def ignore_event(**kwarg):
    pass

class NetTestController:
    def __init__(self, recipe_path, log_ctl, cleanup=False,
                 res_serializer=None, config=None):
        self._docleanup = cleanup
        self._res_serializer = res_serializer
        self._remote_capture_files = {}
        self._config = config
        self._log_ctl = log_ctl
        self._recipe_path = recipe_path
        self._msg_dispatcher = MessageDispatcher(log_ctl)

        sp = SlavePool(config.get_option('environment', 'pool_dirs'),
                       check_process_running("libvirtd"), config)
        self._slave_pool = sp

        self._machines = {}
        self._network_bridges = {}

        self._recipe = recipe = {}
        recipe["networks"] = {}
        recipe["machines"] = {}
        recipe["switches"] = {}

        mac_pool_range = config.get_option('environment', 'mac_pool_range')
        self._mac_pool = MacPool(mac_pool_range[0], mac_pool_range[1])

        parser = RecipeParse(recipe_path)
        parser.set_target(self._recipe)
        parser.set_machines(self._machines)

        parser.register_event_handler("provisioning_requirements_ready",
                                        self._prepare_provisioning)
        parser.register_event_handler("interface_config_ready",
                                        self._prepare_interface)

        modules_dirs = config.get_option('environment', 'module_dirs')
        tools_dirs = config.get_option('environment', 'tool_dirs')

        self._resource_table = {}
        self._resource_table["module"] = self._load_test_modules(modules_dirs)
        self._resource_table["tools"] = self._load_test_tools(tools_dirs)

        self._parser = parser

    def _get_machineinfo(self, machine_id):
        try:
            info = self._recipe["machines"][machine_id]["params"]
        except KeyError:
            msg = "Machine parameters requested, but not yet available"
            raise NetTestError(msg)

        return info

    @staticmethod
    def _session_die(session, status):
        logging.debug("%s terminated with status %s", session.command, status)
        msg = "SSH session terminated with status %s" % status
        raise NetTestError(msg)

    def _prepare_provisioning(self):
        machines = self._recipe["machines"]
        if len(machines) <= 0:
            return

        sp = self._slave_pool
        machines = sp.provision_machines(machines)
        if machines == None:
            msg = "This setup cannot be provisioned with the current pool."
            raise NetTestError(msg)

        for m_id, machine in machines.iteritems():
            self._machines[m_id] = machine

        logging.info("Provisioning initialized")
        for m_id in machines.keys():
            provisioner = sp.get_provisioner_id(m_id)
            logging.info("  machine %s uses %s" % (m_id, provisioner))

        for m_id in machines.keys():
            self._prepare_machine(m_id)

    def _prepare_machine(self, m_id):
        machine = self._machines[m_id]
        address = socket.gethostbyname(machine.get_hostname())

        self._log_ctl.add_slave(m_id, address)
        port = self._config.get_option('environment', 'rpcport')
        machine.set_rpc(self._msg_dispatcher, port)
        machine.set_mac_pool(self._mac_pool)

        recipe_name = os.path.basename(self._recipe_path)
        machine.configure(recipe_name, self._docleanup)
        machine.sync_resources(self._resource_table)

    def _prepare_interface(self, machine_id, if_id):
        machine = self._machines[machine_id]
        ifconfig = self._recipe["machines"][machine_id]["interfaces"][if_id]
        if_type = ifconfig["type"]

        try:
            iface = machine.get_interface(if_id)
        except MachineError:
            iface = machine.new_soft_interface(if_id, if_type)

        if "slaves" in ifconfig:
            for slave_id in ifconfig["slaves"]:
                iface.add_slave(machine.get_interface(slave_id))

        if "addresses" in ifconfig:
            for addr in ifconfig["addresses"]:
                iface.add_address(addr)

        if "options" in ifconfig:
            for name, value in ifconfig["options"]:
                iface.set_option(name, value)

        iface.configure()

    def _cleanup_slaves(self, deconfigure=True):
        if self._machines == None:
            return

        for machine_id, machine in self._machines.iteritems():
            if machine.is_configured():
                machine.cleanup()

                #clean-up slave logger
                self._log_ctl.remove_slave(machine_id)

        # remove dynamically created bridges
        for bridge in self._network_bridges:
            bridge.cleanup()

    def _prepare(self):
        # All the perparations are made within the recipe parsing
        # This is achieved by handling parser events
        try:
            self._parser.parse_recipe()
        except Exception as exc:
            logging.debug("Exception raised during recipe parsing. "\
                    "Deconfiguring machines.")
            log_exc_traceback()
            self._cleanup_slaves()
            raise NetTestError(exc)

    def _run_command(self, command):
        if "desc" in command:
            logging.info("Cmd description: %s", desc)

        if command["type"] == "ctl_wait":
            sleep(command["value"])
            cmd_res = {"passed" : True}
            return cmd_res

        machine_id = command["machine_id"]
        machine = self._machines[machine_id]

        cmd_res = machine.run_command(command)
        return cmd_res

    def _run_command_sequence(self, sequence):
        seq_passed = True
        for command in sequence["commands"]:
            logging.info("Executing command: [%s]", str_command(command))
            cmd_res = self._run_command(command)
            if self._res_serializer:
                self._res_serializer.add_cmd_result(command, cmd_res)
            logging.debug("Result: %s", str(cmd_res))
            if "res_data" in cmd_res:
                res_data = pformat(cmd_res["res_data"])
                logging.info("Result data: %s", (res_data))
            if not cmd_res["passed"]:
                logging.error("Command failed: [%s], Error message: \"%s\"",
                              str_command(command), cmd_res["err_msg"])
                seq_passed = False
        return seq_passed

    def dump_recipe(self):
        self._prepare()
        pprint(self._recipe)
        self._cleanup_slaves()
        return True

    def config_only_recipe(self):
        self._prepare()
        self._cleanup_slaves(deconfigure=False)
        return True

    def run_recipe(self, packet_capture=False):
        self._prepare()

        if packet_capture:
            self._start_packet_capture()

        err = None
        try:
            res = self._run_recipe()
        except ServerException as exc:
            err = NetTestError(exc)
        except Exception as exc:
            logging.info("Recipe execution terminated by unexpected exception")
            log_exc_traceback()
            err = exc

        if packet_capture:
            self._stop_packet_capture()
            self._gather_capture_files()

        self._cleanup_slaves()

        if not err:
            return res
        else:
            raise err

    def _run_recipe(self):
        overall_res = True

        for sequence in self._recipe["sequences"]:
            try:
                res = self._run_command_sequence(sequence)
            except CommandException as exc:
                logging.debug(exc)
                overall_res = False
                break

            for machine in self._machines.itervalues():
                machine.restore_system_config()

            # sequence failed, check if we should quit_on_fail
            if not res:
                overall_res = False
                if sequence["quit_on_fail"] == "yes":
                    break

        return overall_res

    def _start_packet_capture(self):
        logging.info("Starting packet capture")
        for machine_id, machine in self._machines.iteritems():
            capture_files = machine.start_packet_capture()
            self._remote_capture_files[machine_id] = capture_files

    def _stop_packet_capture(self):
        logging.info("Stopping packet capture")
        for machine_id, machine in self._machines.iteritems():
            machine.stop_packet_capture()

    # TODO: Move this function to logging
    def _gather_capture_files(self):
        logging_root = self._log_ctl.get_recipe_log_path()
        logging_root = os.path.abspath(logging_root)
        logging.info("Retrieving capture files from slaves")
        for machine_id, machine in self._machines.iteritems():
            hostname = machine.get_hostname()

            slave_logging_dir = os.path.join(logging_root, hostname + "/")
            try:
                os.mkdir(slave_logging_dir)
            except OSError as err:
                if err.errno != 17:
                    msg = "Cannot access the logging directory %s" \
                                            % slave_logging_dir
                    raise NetTestError(msg)

            capture_files = self._remote_capture_files[machine_id]
            for if_id, remote_path in capture_files.iteritems():
                filename = "%s.pcap" % if_id
                local_path = os.path.join(slave_logging_dir, filename)
                machine.copy_file_from_machine(remote_path, local_path)

            logging.info("pcap files from machine %s stored at %s",
                            machine_id, slave_logging_dir)

    def _load_test_modules(self, dirs):
        modules = {}
        for dir_name in dirs:
            files = os.listdir(dir_name)
            for f in files:
                test_path = os.path.abspath("%s/%s" % (dir_name, f))
                if os.path.isfile(test_path):
                    match = re.match("Test(.+)\.py$", f)
                    if match:
                        test_name = match.group(1)
                        test_hash = md5sum(test_path)

                        if test_name in modules:
                            msg = "Overriding previously defined test '%s' " \
                                  "from %s with a different one located in " \
                                  "%s" % (test_name, test_path,
                                    modules[test_name]["path"])
                            logging.warn(msg)

                        modules[test_name] = {"path": test_path,
                                              "hash": test_hash}
        return modules

    def _load_test_tools(self, dirs):
        packages = {}
        for dir_name in dirs:
            files = os.listdir(dir_name)
            for f in files:
                pkg_path = os.path.abspath("%s/%s" % (dir_name, f))
                if os.path.isdir(pkg_path):
                    pkg_name = os.path.basename(pkg_path.rstrip("/"))
                    pkg_hash = dir_md5sum(pkg_path)

                    if pkg_name in packages:
                        msg = "Overriding previously defined tools " \
                              "package '%s' from %s with a different " \
                              "one located in %s" % (pkg_name, pkg_path,
                                            packages[pkg_name]["path"])
                        logging.warn(msg)

                    packages[pkg_name] = {"path": pkg_path,
                                           "hash": pkg_hash}
        return packages

class MessageDispatcher(ConnectionHandler):
    def __init__(self, log_ctl):
        super(MessageDispatcher, self).__init__()
        self._log_ctl = log_ctl

    def add_slave(self, machine_id, connection):
        self.add_connection(machine_id, connection)

    def send_message(self, machine_id, data):
        soc = self.get_connection(machine_id)

        if send_data(soc, data) == False:
            msg = "Connection error from slave %s" % machine_id
            raise NetTestError(msg)

    def wait_for_result(self, machine_id):
        wait = True
        while wait:
            messages = self.check_connections()
            for msg in messages:
                if msg[1]["type"] == "result" and msg[0] == machine_id:
                    wait = False
                    result = msg[1]["result"]
                else:
                    self._process_message(msg)

        return result

    def _process_message(self, message):
        if message[1]["type"] == "log":
            record = message[1]["record"]
            self._log_ctl.add_client_log(message[0], record)
        elif message[1]["type"] == "result":
            msg = "Recieved result message from different slave %s" % message[0]
            logging.debug(msg)
        elif message[1]["type"] == "exception":
            msg = "Recieved an exception from slave: %s" % message[0]
            raise CommandException(msg)
        else:
            msg = "Unknown message type: %s" % message[1]["type"]
            raise NetTestError(msg)

    def disconnect_slave(self, machine_id):
        soc = self.get_connection(machine_id)
        self.remove_connection(soc)
