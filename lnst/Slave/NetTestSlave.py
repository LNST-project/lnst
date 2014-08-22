"""
This module defines NetConfigSlave class which does spawns xmlrpc server and
runs controller's commands

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import signal
import select, logging
import os
import sys, traceback
import datetime
import socket
import dbus
import ctypes
import multiprocessing
from time import sleep
from xmlrpclib import Binary
from tempfile import NamedTemporaryFile
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.PacketCapture import PacketCapture
from lnst.Common.Utils import die_when_parent_die
from lnst.Common.NetUtils import scan_netdevs, test_tcp_connection
from lnst.Common.NetUtils import normalize_hwaddr
from lnst.Common.ExecCmd import exec_cmd, ExecCmdFail
from lnst.Common.ResourceCache import ResourceCache
from lnst.Common.NetTestCommand import NetTestCommandContext
from lnst.Common.NetTestCommand import CommandException, NetTestCommand
from lnst.Slave.NmConfigDevice import is_nm_managed_by_name
from lnst.Common.Utils import check_process_running
from lnst.Common.ConnectionHandler import recv_data, send_data
from lnst.Common.ConnectionHandler import ConnectionHandler
from lnst.Common.Config import lnst_config
from lnst.Common.Config import DefaultRPCPort
from lnst.Common.NetTestCommand import NetTestCommandConfig
from lnst.Slave.InterfaceManager import InterfaceManager

class SlaveMethods:
    '''
    Exported xmlrpc methods
    '''
    def __init__(self, command_context, log_ctl, if_manager, net_namespaces,
                 server_handler, slave_server):
        self._packet_captures = {}
        self._if_manager = if_manager
        self._command_context = command_context
        self._log_ctl = log_ctl
        self._net_namespaces = net_namespaces
        self._server_handler = server_handler
        self._slave_server = slave_server

        self._capture_files = {}
        self._copy_targets = {}
        self._copy_sources = {}
        self._system_config = {}

        self._cache = ResourceCache(lnst_config.get_option("cache", "dir"),
                        lnst_config.get_option("cache", "expiration_period"))

        self._resource_table = {'module': {}, 'tools': {}}

        self._bkp_nm_opt_val = lnst_config.get_option("environment", "use_nm")

    def hello(self, recipe_path):
        self.machine_cleanup()
        self.restore_nm_option()

        logging.info("Recieved a controller connection.")
        self.clear_resource_table()
        self._cache.del_old_entries()
        self.reset_file_transfers()

        self._if_manager.rescan_devices()

        date = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        self._log_ctl.set_recipe(recipe_path, expand=date)
        sleep(1)

        if check_process_running("NetworkManager"):
            logging.warning("=============================================")
            logging.warning("NetworkManager is running on a slave machine!")
            if lnst_config.get_option("environment", "use_nm"):
                logging.warning("Support of NM is still experimental!")
            else:
                logging.warning("Usage of NM is disabled!")
            logging.warning("=============================================")
        return "hello"

    def bye(self):
        self.restore_system_config()
        self.clear_resource_table()
        self._cache.del_old_entries()
        self.reset_file_transfers()
        self._remove_capture_files()

        for netns in self._net_namespaces.keys():
            self.del_namespace(netns)
        self._net_namespaces = {}
        return "bye"

    def kill_cmds(self):
        logging.info("Killing all forked processes.")
        self._command_context.cleanup()
        return "Commands killed"

    def map_if_by_hwaddr(self, if_id, hwaddr):
        devices = self.get_devices_by_hwaddr(hwaddr)

        if len(devices) == 1:
            dev = self._if_manager.get_device_by_hwaddr(hwaddr)
            self._if_manager.map_if(if_id, dev.get_if_index())

        return devices

    def get_devices_by_devname(self, devname):
        name_scan = self._if_manager.get_devices()
        netdevs = []

        for entry in name_scan:
            if entry["name"] == devname:
                netdevs.append(entry)

        return netdevs

    def get_devices_by_hwaddr(self, hwaddr):
        devices = self._if_manager.get_devices()
        matched = []
        for dev in devices:
            if dev.get_hwaddr() == hwaddr:
                entry = {"name": dev.get_name(),
                         "hwaddr": dev.get_hwaddr()}
                matched.append(entry)

        return matched

    def set_device_up(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        dev.up()
        return True

    def set_device_down(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        dev.down()
        return True

    def set_unmapped_device_down(self, hwaddr):
        dev = self._if_manager.get_device_by_hwaddr(hwaddr)
        dev.down()
        return True

    def configure_interface(self, if_id, config):
        device = self._if_manager.get_mapped_device(if_id)
        device.set_configuration(config)
        device.configure()
        return True

    def create_soft_interface(self, if_id, config):
        dev_name = self._if_manager.create_device_from_config(if_id, config)
        dev = self._if_manager.get_mapped_device(if_id)
        dev.configure()
        return dev_name

    def create_if_pair(self, if_id1, config1, if_id2, config2):
        dev_names = self._if_manager.create_device_pair(if_id1, config1,
                                                        if_id2, config2)
        dev1 = self._if_manager.get_mapped_device(if_id1)
        dev2 = self._if_manager.get_mapped_device(if_id2)

        while dev1.get_if_index() == None and dev2.get_if_index() == None:
            msgs = self._server_handler.get_messages_from_con('netlink')
            for msg in msgs:
                self._if_manager.handle_netlink_msgs(msg[1]["data"])

        if config1["netns"] != None:
            hwaddr = dev1.get_hwaddr()
            self.set_if_netns(if_id1, config1["netns"])

            msg = {"type": "command", "method_name": "map_if_by_hwaddr",
                   "args": [if_id1, hwaddr]}
            self._server_handler.send_data_to_netns(config1["netns"], msg)
            result = self._slave_server.wait_for_result(config1["netns"])
            if len(result["result"]) != 1:
                raise Exception("Mapping failed.")

            msg = {"type": "command", "method_name": "configure_interface",
                   "args": [if_id1, config1]}
            self._server_handler.send_data_to_netns(config1["netns"], msg)
            result = self._slave_server.wait_for_result(config1["netns"])
            if result["result"] != True:
                raise Exception("Configuration failed.")
        else:
            dev1.configure()
        if config2["netns"] != None:
            hwaddr = dev2.get_hwaddr()
            self.set_if_netns(if_id2, config2["netns"])

            msg = {"type": "command", "method_name": "map_if_by_hwaddr",
                   "args": [if_id2, hwaddr]}
            self._server_handler.send_data_to_netns(config2["netns"], msg)
            result = self._slave_server.wait_for_result(config2["netns"])
            if len(result["result"]) != 1:
                raise Exception("Mapping failed.")

            msg = {"type": "command", "method_name": "configure_interface",
                   "args": [if_id2, config2]}
            self._server_handler.send_data_to_netns(config2["netns"], msg)
            result = self._slave_server.wait_for_result(config2["netns"])
            if result["result"] != True:
                raise Exception("Configuration failed.")
        else:
            dev2.configure()
        return dev_names

    def deconfigure_if_pair(self, if_id1, if_id2):
        dev1 = self._if_manager.get_mapped_device(if_id1)
        dev2 = self._if_manager.get_mapped_device(if_id2)

        if dev1.get_netns() == None:
            dev1.deconfigure()
        else:
            netns = dev1.get_netns()

            msg = {"type": "command", "method_name": "deconfigure_interface",
                   "args": [if_id1]}
            self._server_handler.send_data_to_netns(netns, msg)
            result = self._slave_server.wait_for_result(netns)
            if result["result"] != True:
                raise Exception("Deconfiguration failed.")

            self.return_if_netns(if_id1)

        if dev2.get_netns() == None:
            dev2.deconfigure()
        else:
            netns = dev2.get_netns()

            msg = {"type": "command", "method_name": "deconfigure_interface",
                   "args": [if_id2]}
            self._server_handler.send_data_to_netns(netns, msg)
            result = self._slave_server.wait_for_result(netns)
            if result["result"] != True:
                raise Exception("Deconfiguration failed.")

            self.return_if_netns(if_id2)

        dev1.destroy()
        dev2.destroy()
        dev1.del_configuration()
        dev2.del_configuration()
        return True

    def deconfigure_interface(self, if_id):
        device = self._if_manager.get_mapped_device(if_id)
        device.clear_configuration()
        return True

    def start_packet_capture(self, filt):
        files = {}
        for if_id, dev in self._if_manager.get_mapped_devices().iteritems():
            if dev.get_netns() != None:
                continue
            dev_name = dev.get_name()

            df_handle = NamedTemporaryFile(delete=False)
            dump_file = df_handle.name
            df_handle.close()

            files[if_id] = dump_file

            pcap = PacketCapture()
            pcap.set_interface(dev_name)
            pcap.set_output_file(dump_file)
            pcap.set_filter(filt)
            pcap.start()

            self._packet_captures[if_id] = pcap

        self._capture_files = files
        return files

    def stop_packet_capture(self):
        if self._packet_captures == None:
            return True

        for if_index, pcap in self._packet_captures.iteritems():
            pcap.stop()

        self._packet_captures.clear()

        return True

    def _remove_capture_files(self):
        for key, name in self._capture_files.iteritems():
            logging.debug("Removing temporary packet capture file %s", name)
            os.unlink(name)

        self._capture_files.clear()

    def _update_system_config(self, options, persistent):
        system_config = self._system_config
        for opt in options:
            option = opt["name"]
            prev = opt["previous_val"]
            curr = opt["current_val"]

            if persistent:
                if option in system_config:
                    del system_config[option]
            else:
                if not option in system_config:
                    system_config[option] = {"initial_val": prev}
                system_config[option]["current_val"] = curr

    def restore_system_config(self):
        logging.info("Restoring system configuration")
        for option, values in self._system_config.iteritems():
            try:
                cmd_str = "echo \"%s\" >%s" % (values["initial_val"], option)
                (stdout, stderr) = exec_cmd(cmd_str)
            except ExecCmdFail:
                logging.warn("Unable to restore '%s' config option!", option)
                return False

        self._system_config = {}
        return True

    def run_command(self, command):
        cmd = NetTestCommand(self._command_context, command,
                                    self._resource_table, self._log_ctl)
        self._command_context.add_cmd(cmd)

        res = cmd.run()
        if not cmd.forked():
            self._command_context.del_cmd(cmd)

        if command["type"] == "config":
            if res["passed"]:
                self._update_system_config(res["res_data"]["options"],
                                           command["persistent"])
            else:
                err = "Error occured while setting system "\
                      "configuration (%s)" % res["res_data"]["err_msg"]
                logging.error(err)

        return res

    def kill_command(self, id):
        cmd = self._command_context.get_cmd(id)
        cmd.kill(None)
        self._command_context.del_cmd(cmd)
        return cmd.get_result()

    def machine_cleanup(self):
        logging.info("Performing machine cleanup.")
        self._command_context.cleanup()
        self._if_manager.deconfigure_all()

        for netns in self._net_namespaces.keys():
            self.del_namespace(netns)
        self._net_namespaces = {}

        self._if_manager.clear_if_mapping()
        self._cache.del_old_entries()
        self.restore_system_config()
        self._remove_capture_files()
        return True

    def clear_resource_table(self):
        self._resource_table = {'module': {}, 'tools': {}}
        return True

    def has_resource(self, res_hash):
        if self._cache.query(res_hash):
            return True

        return False

    def map_resource(self, res_hash, res_type, res_name):
        resource_location = self._cache.get_path(res_hash)

        if not res_type in self._resource_table:
            self._resource_table[res_type] = {}

        self._resource_table[res_type][res_name] = resource_location
        self._cache.renew_entry(res_hash)

        return True

    def add_resource_to_cache(self, file_hash, local_path, name,
                                res_hash, res_type):
        self._cache.add_cache_entry(file_hash, local_path, name, res_type)
        return True

    def start_copy_to(self, filepath=None):
        if filepath in self._copy_targets:
            return ""

        if filepath:
            self._copy_targets[filepath] = open(filepath, "w+b")
        else:
            tmpfile = NamedTemporaryFile("w+b", delete=False)
            filepath = tmpfile.name
            self._copy_targets[filepath] = tmpfile

        return filepath

    def copy_part_to(self, filepath, binary_data):
        if self._copy_targets[filepath]:
            self._copy_targets[filepath].write(binary_data.data)
            return True

        return False

    def finish_copy_to(self, filepath):
        if self._copy_targets[filepath]:
            self._copy_targets[filepath].close()

            del self._copy_targets[filepath]
            return True

        return False

    def start_copy_from(self, filepath):
        if filepath in self._copy_sources or not os.path.exists(filepath):
            return False

        self._copy_sources[filepath] = open(filepath, "rb")
        return True

    def copy_part_from(self, filepath, buffsize):
        data = Binary(self._copy_sources[filepath].read(buffsize))
        return data

    def finish_copy_from(self, filepath):
        if filepath in self._copy_sources:
            self._copy_sources[filepath].close()
            del self._copy_sources[filepath]
            return True

        return False

    def reset_file_transfers(self):
        for file_handle in self._copy_targets.itervalues():
            file_handle.close()
        self._copy_targets = {}

        for file_handle in self._copy_sources.itervalues():
            file_handle.close()
        self._copy_sources = {}

    def enable_nm(self):
        logging.warning("====================================================")
        logging.warning("Enabling use of NetworkManager on controller request")
        logging.warning("====================================================")
        val = lnst_config.get_option("environment", "use_nm")
        lnst_config.set_option("environment", "use_nm", True)
        return val

    def disable_nm(self):
        logging.warning("=====================================================")
        logging.warning("Disabling use of NetworkManager on controller request")
        logging.warning("=====================================================")
        val = lnst_config.get_option("environment", "use_nm")
        lnst_config.set_option("environment", "use_nm", False)
        return val

    def restore_nm_option(self):
        val = lnst_config.get_option("environment", "use_nm")
        if val == self._bkp_nm_opt_val:
            return val
        logging.warning("=========================================")
        logging.warning("Restoring use_nm option to original value")
        logging.warning("=========================================")
        lnst_config.set_option("environment", "use_nm", self._bkp_nm_opt_val)
        return val

    def add_namespace(self, netns):
        if netns in self._net_namespaces:
            logging.debug("Network namespace %s already exists." % netns)
        else:
            logging.debug("Creating network namespace %s." % netns)
            read_pipe, write_pipe = multiprocessing.Pipe()
            pid = os.fork()
            if pid != 0:
                self._net_namespaces[netns] = {"pid": pid,
                                               "pipe": read_pipe}
                self._server_handler.add_netns(netns, read_pipe)
                return None
            elif pid == 0:
                #create new network namespace
                libc_name = ctypes.util.find_library("c")
                #from sched.h
                CLONE_NEWNET = 0x40000000
                CLONE_NEWNS = 0x00020000
                #based on ipnetns.c from the iproute2 project
                MNT_DETACH = 0x00000002
                MS_SLAVE = 1<<19
                MS_REC = 16384

                libc = ctypes.CDLL(libc_name)
                libc.unshare(CLONE_NEWNET)
                #based on ipnetns.c from the iproute2 project
                libc.unshare(CLONE_NEWNS)
                libc.mount("", "/", "none", MS_SLAVE | MS_REC, 0)
                libc.umount2("/sys", MNT_DETACH)
                libc.mount(netns, "/sys", "sysfs", 0, 0)

                #set ctl socket to pipe to main netns
                self._server_handler.close_s_sock()
                self._server_handler.close_c_sock()
                self._server_handler.clear_connections()
                self._server_handler.clear_netns_connections()

                self._if_manager.reconnect_netlink()
                self._server_handler.add_connection('netlink',
                                            self._if_manager.get_nl_socket())

                self._server_handler.set_netns(netns)
                self._server_handler.set_ctl_sock((write_pipe, "root_netns"))

                self._log_ctl.disable_logging()
                self._log_ctl.set_connection(write_pipe)

                self._if_manager.rescan_devices()
                logging.debug("Created network namespace %s" % netns)
                return True
            else:
                raise Exception("Fork failed!")

    def del_namespace(self, netns):
        if netns not in self._net_namespaces:
            logging.debug("Network namespace %s doesn't exist." % netns)
            return False
        else:
            netns_pid = self._net_namespaces[netns]["pid"]
            os.kill(netns_pid, signal.SIGTERM)
            os.waitpid(netns_pid, 0)
            logging.debug("Network namespace %s removed." % netns)

            self._net_namespaces[netns]["pipe"].close()
            self._server_handler.del_netns(netns)
            del self._net_namespaces[netns]
            return True

    def set_if_netns(self, if_id, netns):
        netns_pid = self._net_namespaces[netns]["pid"]

        device = self._if_manager.get_mapped_device(if_id)
        dev_name = device.get_name()
        device.set_netns(netns)

        exec_cmd("ip link set %s netns %d" % (dev_name, netns_pid))
        return True

    def return_if_netns(self, if_id):
        device = self._if_manager.get_mapped_device(if_id)
        if device.get_netns() == None:
            dev_name = device.get_name()
            ppid = os.getppid()
            exec_cmd("ip link set %s netns %d" % (dev_name, ppid))
            return True
        else:
            netns = device.get_netns()
            msg = {"type": "command", "method_name": "return_if_netns",
                   "args": [if_id]}
            self._server_handler.send_data_to_netns(netns, msg)
            result = self._slave_server.wait_for_result(netns)
            if result["result"] != True:
                raise Exception("Return from netns failed.")

            device.set_netns(None)
            return True

class ServerHandler(object):
    def __init__(self, addr):
        self._connection_handler = ConnectionHandler()
        self._netns_con_handler = ConnectionHandler()
        try:
            self._s_socket = socket.socket()
            self._s_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._s_socket.bind(addr)
            self._s_socket.listen(1)
        except socket.error as e:
            logging.error(e[1])
            exit(1)

        self._c_socket = None
        self._netns = None

    def accept_connection(self):
        self._c_socket, addr = self._s_socket.accept()
        self._c_socket = (self._c_socket, addr[0])
        logging.info("Recieved connection from %s" % self._c_socket[1])

        self._connection_handler.add_connection(self._c_socket[1],
                                                self._c_socket[0])
        return self._c_socket

    def get_ctl_sock(self):
        if self._c_socket != None:
            return self._c_socket[0]
        else:
            return None

    def set_ctl_sock(self, sock):
        if self._c_socket != None:
            self._c_socket.close()
            self._c_socket = None
        self._c_socket = sock
        self._connection_handler.add_connection(self._c_socket[1],
                                                self._c_socket[0])

    def close_s_sock(self):
        self._s_socket.close()
        self._s_socket = None

    def close_c_sock(self):
        self._c_socket[0].close()
        self._connection_handler.remove_connection(self._c_socket[0])
        self._c_socket = None

    def get_messages(self):
        messages = self._connection_handler.check_connections()
        messages += self._netns_con_handler.check_connections()

        #push ctl messages to the end of message queue, this ensures that
        #update messages are handled first
        ctl_msgs = []
        non_ctl_msgs = []
        for msg in messages:
            if msg[0] == self._c_socket[1]:
                ctl_msgs.append(msg)
            else:
                non_ctl_msgs.append(msg)
        messages = non_ctl_msgs + ctl_msgs

        addr = self._c_socket[1]
        if self._connection_handler.get_connection(addr) == None:
            logging.info("Lost controller connection.")
            self._c_socket = None
        return messages

    def get_messages_from_con(self, con_id):
        if self._connection_handler.get_connection(con_id) != None:
            return self._connection_handler.check_connections_by_id([con_id])
        elif self._netns_con_handler.get_connection(con_id) != None:
            return self._netns_con_handler.check_connections_by_id([con_id])
        else:
            raise Exception("Unknown connection id '%s'." % con_id)

    def send_data_to_ctl(self, data):
        if self._c_socket != None:
            if self._netns != None:
                data = {"type": "from_netns",
                        "netns": self._netns,
                        "data": data}
            return send_data(self._c_socket[0], data)
        else:
            return False

    def send_data_to_netns(self, netns, data):
        netns_con = self._netns_con_handler.get_connection(netns)
        if netns_con == None:
            raise Exception("No such namespace!")
        else:
            return send_data(netns_con, data)

    def add_connection(self, id, connection):
        self._connection_handler.add_connection(id, connection)

    def remove_connection(self, key):
        connection = self._connection_handler.get_connection(key)
        self._connection_handler.remove_connection(connection)

    def clear_connections(self):
        self._connection_handler.clear_connections()

    def update_connections(self, connections):
        for key, connection in connections.iteritems():
            self.remove_connection(key)
            self.add_connection(key, connection)

    def set_netns(self, netns):
        self._netns = netns

    def add_netns(self, netns, connection):
        self._netns_con_handler.add_connection(netns, connection)

    def del_netns(self, netns):
        connection = self._netns_con_handler.get_connection(netns)
        self._netns_con_handler.remove_connection(connection)

    def clear_netns_connections(self):
        self._netns_con_handler.clear_connections()

class NetTestSlave:
    def __init__(self, log_ctl, port = DefaultRPCPort):
        die_when_parent_die()

        self._cmd_context = NetTestCommandContext()
        self._server_handler = ServerHandler(("", port))
        self._if_manager = InterfaceManager(self._server_handler)

        self._net_namespaces = {}

        self._methods = SlaveMethods(self._cmd_context, log_ctl,
                                     self._if_manager, self._net_namespaces,
                                     self._server_handler, self)

        self.register_die_signal(signal.SIGHUP)
        self.register_die_signal(signal.SIGINT)
        self.register_die_signal(signal.SIGTERM)

        self._finished = False

        self._log_ctl = log_ctl

        self._server_handler.add_connection('netlink',
                                            self._if_manager.get_nl_socket())

    def run(self):
        while not self._finished:
            if self._server_handler.get_ctl_sock() == None:
                self._log_ctl.cancel_connection()
                try:
                    logging.info("Waiting for connection.")
                    self._server_handler.accept_connection()
                except socket.error:
                    continue
                self._log_ctl.set_connection(
                                            self._server_handler.get_ctl_sock())

            msgs = self._server_handler.get_messages()

            for msg in msgs:
                self._process_msg(msg[1])

        self._methods.machine_cleanup()

    def wait_for_result(self, id):
        result = None
        while result == None:
            msgs = self._server_handler.get_messages_from_con(id)
            for msg in msgs:
                if msg[1]["type"] == "result":
                    result = msg[1]
                elif msg[1]["type"] == "from_netns" and\
                     msg[1]["data"]["type"] == "result":
                    result = msg[1]["data"]
                else:
                    self._process_msg(msg[1])
        return result

    def _process_msg(self, msg):
        if msg["type"] == "command":
            method = getattr(self._methods, msg["method_name"], None)
            if method != None:
                try:
                    result = method(*msg["args"])
                except:
                    log_exc_traceback()
                    type, value, tb = sys.exc_info()
                    exc_trace = ''.join(traceback.format_exception(type,
                                                                   value, tb))
                    response = {"type": "exception", "Exception": value}

                    self._server_handler.send_data_to_ctl(response)
                    return

                if result != None:
                    response = {"type": "result", "result": result}
                    self._server_handler.send_data_to_ctl(response)
            else:
                err = "Method '%s' not supported." % msg["method_name"]
                response = {"type": "error", "err": err}
                self._server_handler.send_data_to_ctl(response)
        elif msg["type"] == "log":
            logger = logging.getLogger()
            record = logging.makeLogRecord(msg["record"])
            logger.handle(record)
        elif msg["type"] == "exception":
            if msg["cmd_id"] != None:
                logging.debug("Recieved an exception from command with id: %s"
                                % msg["cmd_id"])
            else:
                logging.debug("Recieved an exception from foreground command")
            logging.debug(msg["Exception"])
            cmd = self._cmd_context.get_cmd(msg["cmd_id"])
            cmd.join()
            self._cmd_context.del_cmd(cmd)
            self._server_handler.send_data_to_ctl(msg)
        elif msg["type"] == "result":
            if msg["cmd_id"] == None:
                del msg["cmd_id"]
                self._server_handler.send_data_to_ctl(msg)
                cmd = self._cmd_context.get_cmd(None)
                cmd.join()
                self._cmd_context.del_cmd(cmd)
            else:
                cmd = self._cmd_context.get_cmd(msg["cmd_id"])
                cmd.join()
                del msg["cmd_id"]

                cmd.set_result(msg["result"])
                if cmd.finished():
                    msg["result"] = cmd.get_result()
                    self._server_handler.send_data_to_ctl(msg)
                    self._cmd_context.del_cmd(cmd)
        elif msg["type"] == "netlink":
            self._if_manager.handle_netlink_msgs(msg["data"])
        elif msg["type"] == "from_netns":
            self._server_handler.send_data_to_ctl(msg["data"])
        elif msg["type"] == "to_netns":
            netns = msg["netns"]
            self._server_handler.send_data_to_netns(netns, msg["data"])
        else:
            raise Exception("Recieved unknown command")

        pipes = self._cmd_context.get_read_pipes()
        self._server_handler.update_connections(pipes)

    def register_die_signal(self, signum):
        signal.signal(signum, self._signal_die_handler)

    def _signal_die_handler(self, signum, frame):
        logging.info("Caught signal %d -> dying" % signum)
        self._finished = True
