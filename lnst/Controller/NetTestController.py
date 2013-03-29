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
from lnst.Controller.NetTestParse import NetTestParse
from lnst.Controller.SlavePool import SlavePool
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
        self._msg_dispatcher = MessageDispatcher()

        sp = SlavePool(config.get_option('environment', 'pool_dirs'),
                       check_process_running("libvirtd"))
        self._slave_pool = sp

        self._recipe = recipe = {}
        recipe["networks"] = {}
        recipe["machines"] = {}
        recipe["provisioning"] = {}
        recipe["switches"] = {}

        mac_pool_range = config.get_option('environment', 'mac_pool_range')
        self._mac_pool = MacPool(mac_pool_range[0],
                                 mac_pool_range[1])

        ntparse = NetTestParse(recipe_path)
        ntparse.set_recipe(self._recipe)

        ntparse.register_event_handler("provisioning_requirements_ready",
                                        self._prepare_provisioning)
        ntparse.register_event_handler("machine_ready",
                                        self._prepare_slave)
        ntparse.register_event_handler("interface_config_ready",
                                        self._prepare_interface)

        modules_dirs = config.get_option('environment', 'module_dirs')
        tools_dirs = config.get_option('environment', 'tool_dirs')

        self._resource_table = {}
        self._resource_table["module"] = self._load_test_modules(modules_dirs)
        self._resource_table["tools"] = self._load_test_tools(tools_dirs)

        self._ntparse = ntparse

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
        provisioning = self._recipe["provisioning"]
        if len(provisioning["setup_requirements"]) <= 0:
            return

        sp = self._slave_pool
        machines = sp.provision_setup(provisioning["setup_requirements"])
        if machines == None:
            msg = "This setup cannot be provisioned with the current pool."
            raise NetTestError(msg)

        for m_id, machine in machines.iteritems():
            self._recipe["machines"][m_id] = machine
        provisioning["map"] = {}

        logging.info("Provisioning initialized")
        for m_id in machines.keys():
            provisioner = sp.get_provisioner_id(m_id)
            provisioning["map"][m_id] = provisioner
            logging.info("  machine %s uses %s" % (m_id, provisioner))

            machines[m_id]["params"]["system_config"] = {}

    def _prepare_device(self, machine_id, dev_id):
        info = self._get_machineinfo(machine_id)
        dev = self._recipe["machines"][machine_id]["netdevices"][dev_id]

        dev_net_name = dev["network"]
        networks = self._recipe["networks"]
        if not dev_net_name in networks:
            networks[dev_net_name] = {"members": []}

        dev_net = networks[dev_net_name]
        dev_net["members"].append((machine_id, dev_id))

        if dev["create"] == "libvirt":
            if not "virt_domain_ctl" in info:
                msg = "Cannot create device. " \
                      "Machine '%s' is not virtual." % (machine_id)
                raise NetTestError(msg)

            if "hwaddr" in dev:
                query_result = self._rpc_call(machine_id,
                        'get_devices_by_hwaddr', dev["hwaddr"])
                if query_result:
                    msg = "Device with hwaddr %s already exists" \
                                                % dev["hwaddr"]
                    raise NetTestError(msg)
            else:
                while True:
                    dev["hwaddr"] = self._mac_pool.get_addr()
                    query_result = self._rpc_call(machine_id,
                            'get_devices_by_hwaddr', dev["hwaddr"])
                    if not len(query_result):
                        break

            if "libvirt_bridge" in dev:
                brctl = BridgeCtl(dev["libvirt_bridge"])
            else:
                if "default_bridge" in dev_net:
                    brctl = dev_net["default_bridge"]
                else:
                    brctl = BridgeCtl()
                    dev_net["default_bridge"] = brctl

            br_name = brctl.get_name()
            brctl.init()

            logging.info("Creating netdevice %s (%s) on machine %s",
                            dev_id, dev["hwaddr"], machine_id)

            domain_ctl = info["virt_domain_ctl"]
            domain_ctl.attach_interface(dev["hwaddr"], br_name)

            ready_check_func = lambda: self._device_ready(machine_id, dev_id)
            ready = wait_for(ready_check_func, timeout=10)

            if not ready:
                msg = "Netdevice initialization failed." \
                      "Unable to create device %s (%s) on machine %s" \
                                % (dev_id, dev["hwaddr"], machine_id)
                raise NetTestError(msg)

            if 'created_devices' not in info:
                info['created_devices'] = []
            info['created_devices'].append((dev_id, dev))

        phys_devs = self._rpc_call(machine_id,
                'get_devices_by_hwaddr', dev["hwaddr"])
        if len(phys_devs) == 1:
            pass
        elif len(phys_devs) < 1:
            msg = "Device %s not found on machine %s" \
                            % (dev_id, machine_id)
            raise NetTestError(msg)
        elif len(phys_devs) > 1:
            msg = "Multiple netdevices with same address %s on machine %s" \
                                    % (dev["hwaddr"], machine_id)
            raise NetTestError(msg)

    def _device_ready(self, machine_id, dev_id):
        dev = self._recipe["machines"][machine_id]["netdevices"][dev_id]

        devs = self._rpc_call(machine_id,
                'get_devices_by_hwaddr', dev["hwaddr"])
        return len(devs) > 0

    def _prepare_interface(self, machine_id, netdev_config_id):
        info = self._get_machineinfo(machine_id)
        logging.info("Configuring interface %s on %s", netdev_config_id,
                                                        info["hostname"])

        self._configure_interface(machine_id, netdev_config_id)

        if_info = self._rpc_call(machine_id,
                'get_interface_info', netdev_config_id)
        machine = self._recipe["machines"][machine_id]
        if "name" in if_info:
            machine["netconfig"][netdev_config_id]["name"] = if_info["name"]

        info["configured_interfaces"].append(netdev_config_id)

    def _configure_interface(self, machine_id, netdev_config_id):
        netconfig = self._recipe["machines"][machine_id]["netconfig"]
        dev_config = netconfig[netdev_config_id]

        self._rpc_call(machine_id,
                'configure_interface', netdev_config_id, dev_config)

    def _deconfigure_interface(self, machine_id, netdev_config_id):
        self._rpc_call(machine_id, 'deconfigure_interface', netdev_config_id)

    def _prepare_slave(self, machine_id):
        logging.info("Preparing machine %s", machine_id)
        info = self._get_machineinfo(machine_id)

        if "libvirt_domain" in info:
            domain_ctl = VirtDomainCtl(info["libvirt_domain"])
            info["virt_domain_ctl"] = domain_ctl

        self._init_slave_logging(machine_id)
        self._init_slave_rpc(machine_id)

        info["configured_interfaces"] = []

        self._rpc_call(machine_id, "clear_resource_table")
        required = self._resource_table

        if self._docleanup and not info["skip_cleanup"]:
            self._rpc_call(machine_id, 'machine_cleanup')
        else:
            logging.info("Skipping cleanup on machine %s" % machine_id)

        for res_type, resources in self._resource_table.iteritems():
            for res_name, res in resources.iteritems():
                has_resource = self._rpc_call(machine_id, "has_resource",
                                                    res["hash"])
                if not has_resource:
                    msg = "Transfering %s %s to machine %s" % \
                            (res_name, res_type, machine_id)
                    logging.info(msg)

                    local_path = required[res_type][res_name]["path"]

                    if res_type == "tools":
                        archive = tempfile.NamedTemporaryFile(delete=False)
                        archive_path = archive.name
                        archive.close()

                        create_tar_archive(local_path, archive_path, True)
                        local_path = archive_path

                    remote_path = self._copy_to_slave(local_path, machine_id)
                    self._rpc_call(machine_id, "add_resource_to_cache",
                                res["hash"], remote_path, res_name,
                                res["path"], res_type)

                    if res_type == "tools":
                        os.unlink(archive_path)

                self._rpc_call(machine_id, "map_resource",
                            res["hash"], res_type, res_name)

        # Some additional initialization is necessary in case the
        # underlying machine is provisioned from the pool
        prov_id = self._slave_pool.get_provisioner_id(machine_id)
        if prov_id:
            provisioner = self._slave_pool.get_provisioner(machine_id)
            logging.info("Initializing provisioned system (%s)" % prov_id)
            for device in provisioner["netdevices"].itervalues():
                self._rpc_call(machine_id, 'set_device_down', device["hwaddr"])

        machine = self._recipe["machines"][machine_id]
        for dev_id in machine["netdevices"].iterkeys():
            self._prepare_device(machine_id, dev_id)

    def _init_slave_rpc(self, machine_id):
        info = self._get_machineinfo(machine_id)
        hostname = info["hostname"]
        if "rpcport" in info:
            port = info["rpcport"]
        else:
            port = self._config.get_option('environment', 'rpcport')
        logging.info("Connecting to RPC on machine %s", hostname)

        rpc = socket.create_connection((hostname, port))
        self._msg_dispatcher.add_slave(machine_id, rpc, info)

        if self._rpc_call(machine_id, 'hello', self._recipe_path) != "hello":
            msg = "Unable to establish RPC connection to machine %s. " \
                                                        % hostname
            msg += "Handshake failed"
            raise NetTestError(msg)

    def _init_slave_logging(self, machine_id):
        info = self._get_machineinfo(machine_id)
        address = socket.gethostbyname(info["hostname"])

        info['logger'] = self._log_ctl.add_slave(address)

    def _deconfigure_slaves(self):
        if 'machines' not in self._recipe:
            return
        for machine_id in self._recipe["machines"]:
            info = self._get_machineinfo(machine_id)

            if self._msg_dispatcher.get_connection(machine_id):
                self._rpc_call(machine_id, "kill_cmds")
            else:
                continue

            if "configured_interfaces" not in info:
                continue

            for if_id in reversed(info["configured_interfaces"]):
                self._rpc_call(machine_id, 'deconfigure_interface', if_id)

            # detach dynamically created devices
            if "created_devices" not in info:
                continue
            for dev_id, dev in reversed(info["created_devices"]):
                logging.info("Removing netdevice %s (%s) from machine %s",
                                dev_id, dev["hwaddr"], machine_id)
                domain_ctl = info["virt_domain_ctl"]
                domain_ctl.detach_interface(dev["hwaddr"])

            #clean-up slave logger
            address = socket.gethostbyname(info["hostname"])
            self._log_ctl.remove_slave(address)

        # remove dynamically created bridges
        networks = self._recipe["networks"]
        for net in networks.itervalues():
            if "default_bridge" in net:
                net["default_bridge"].cleanup()

    def _disconnect_slaves(self):
        if 'machines' not in self._recipe:
            return

        for machine_id in self._recipe["machines"]:
            if self._msg_dispatcher.get_connection(machine_id):
                self._rpc_call(machine_id, "bye")
                self._msg_dispatcher.disconnect_slave(machine_id)

    def _prepare(self):
        # All the perparations are made within the recipe parsing
        # This is achieved by handling parser events
        try:
            self._ntparse.parse_recipe()
        except Exception as exc:
            logging.debug("Exception raised during recipe parsing. "\
                    "Deconfiguring machines.")
            log_exc_traceback()
            self._deconfigure_slaves()
            self._disconnect_slaves()
            raise NetTestError(exc)

    def _run_command(self, command):
        machine_id = command["machine_id"]
        try:
            desc = command["desc"]
            logging.info("Cmd description: %s", desc)
        except KeyError:
            pass

        if command["type"] == "ctl_wait":
            sleep(command["value"])
            cmd_res = {"passed" : True}
            return cmd_res

        if "timeout" in command:
            timeout = command["timeout"]
            logging.debug("Setting socket timeout to \"%d\"", timeout)
            socket.setdefaulttimeout(timeout)
        try:
            cmd_res = self._rpc_call(machine_id, 'run_command', command)
        except socket.timeout:
            msg = "RPC connection to machine %s timed out" % machine_id
            raise NetTestError(msg)
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
        self._deconfigure_slaves()
        self._disconnect_slaves()
        return True

    def config_only_recipe(self):
        self._prepare()
        self._disconnect_slaves()
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

        self._deconfigure_slaves()
        self._disconnect_slaves()

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

            for machine_id in self._recipe["machines"]:
                self._restore_system_config(machine_id)

            # sequence failed, check if we should quit_on_fail
            if not res:
                overall_res = False
                if sequence["quit_on_fail"] == "yes":
                    break

        return overall_res

    def _start_packet_capture(self):
        logging.info("Starting packet capture")
        for machine_id in self._recipe["machines"]:
            capture_files = self._rpc_call(machine_id,
                    'start_packet_capture', "")
            self._remote_capture_files[machine_id] = capture_files

    def _stop_packet_capture(self):
        logging.info("Stopping packet capture")
        for machine_id in self._recipe["machines"]:
            self._rpc_call(machine_id, 'stop_packet_capture')

    def _gather_capture_files(self):
        logging_root = self._log_root_path
        logging_root = os.path.abspath(logging_root)
        logging.info("Retrieving capture files from slaves")
        for machine_id in self._recipe["machines"]:
            hostname = self._recipe["machines"][machine_id]['info']['hostname']

            slave_logging_dir = os.path.join(logging_root, hostname + "/")
            try:
                os.mkdir(slave_logging_dir)
            except OSError as err:
                if err.errno != 17:
                    msg = "Cannot access the logging directory %s" \
                                            % slave_logging_dir
                    raise NetTestError(msg)

            capture_files = self._remote_capture_files[machine_id]
            for dev_id, remote_path in capture_files.iteritems():
                filename = "%s.pcap" % dev_id
                local_path = os.path.join(slave_logging_dir, filename)
                self._copy_from_slave(machine_id, remote_path, local_path)

            logging.info("pcap files from machine %s stored at %s",
                            machine_id, slave_logging_dir)

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

            seq = {"commands": [command], "quit_on_fail": "no"}
            self._run_command_sequence(seq)
            info["system_config"] = {}

    def _rpc_call(self, machine_id, method_name, *args):
        data = {}
        data["type"] = "command"
        data["method_name"] = method_name
        data["args"] = args

        self._msg_dispatcher.send_message(machine_id, data)

        result = self._msg_dispatcher.wait_for_result(machine_id)

        return result

    def _copy_to_slave(self, local_path, machine_id, remote_path=None):
        remote_path = self._rpc_call(machine_id, "start_copy_to", remote_path)
        f = open(local_path, "rb")

        while True:
            data = f.read(1024*1024) # 1MB buffer
            if len(data) == 0:
                break

            self._rpc_call(machine_id, "copy_part_to",
                                remote_path, Binary(data))

        self._rpc_call(machine_id, "finish_copy_to", remote_path)
        return remote_path

    def _copy_from_slave(self, machine_id, remote_path, local_path):
        status = self._rpc_call(machine_id, "start_copy_from", remote_path)
        if not status:
            raise NetTestError("The requested file cannot be transfered." \
                       "It does not exist on machine %s" % machine_id)

        local_file = open(local_path, "wb")

        binary = "next"
        while binary != "":
            binary = self._rpc_call(machine_id, "copy_part_from",
                                        remote_path, 1024*1024) # 1MB buffer
            local_file.write(binary.data)

        local_file.close()
        self._rpc_call(machine_id, "finish_copy_from", remote_path)

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
    def __init__(self):
        super(MessageDispatcher, self).__init__()
        self._slaves = {}

    def add_slave(self, machine_id, connection, machine_info):
        self._slaves[machine_id] = machine_info
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
            self._add_client_log(message[0], record)
        elif message[1]["type"] == "result":
            msg = "Recieved result message from different slave %s" % message[0]
            logging.debug(msg)
        elif message[1]["type"] == "exception":
            msg = "Recieved an exception from slave: %s" % message[0]
            raise CommandException(msg)
        else:
            msg = "Unknown message type: %s" % message[1]["type"]
            raise NetTestError(msg)

    def _add_client_log(self, machine_id, log_record):
        info = self._slaves[machine_id]
        address = socket.gethostbyname(info['hostname'])
        logger = info['logger']

        log_record['address'] = '(' + address + ')'
        record = logging.makeLogRecord(log_record)
        logger.handle(record)

    def disconnect_slave(self, machine_id):
        del self._slaves[machine_id]
        soc = self.get_connection(machine_id)
        self.remove_connection(soc)
