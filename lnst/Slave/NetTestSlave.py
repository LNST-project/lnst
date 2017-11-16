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
import logging
import os, stat
import sys, traceback
import datetime
import socket
import ctypes
import multiprocessing
import re
import struct
from time import sleep, time
from xmlrpclib import Binary
from tempfile import NamedTemporaryFile
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.PacketCapture import PacketCapture
from lnst.Common.Utils import die_when_parent_die
from lnst.Common.ExecCmd import exec_cmd, ExecCmdFail
from lnst.Common.ResourceCache import ResourceCache
from lnst.Common.NetTestCommand import NetTestCommandContext
from lnst.Common.NetTestCommand import NetTestCommand
from lnst.Common.NetTestCommand import DEFAULT_TIMEOUT
from lnst.Common.Utils import check_process_running
from lnst.Common.Utils import is_installed
from lnst.Common.ConnectionHandler import send_data
from lnst.Common.ConnectionHandler import ConnectionHandler
from lnst.Common.Config import lnst_config
from lnst.Common.Config import DefaultRPCPort
from lnst.Common.Consts import MROUTE
from lnst.Slave.InterfaceManager import InterfaceManager
from lnst.Slave.BridgeTool import BridgeTool
from lnst.Slave.SlaveSecSocket import SlaveSecSocket, SecSocketException

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
        self.mroute_sockets = {}

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

        slave_desc = {}
        if check_process_running("NetworkManager"):
            logging.warning("=============================================")
            logging.warning("NetworkManager is running on a slave machine!")
            if lnst_config.get_option("environment", "use_nm"):
                logging.warning("Support of NM is still experimental!")
            else:
                logging.warning("Usage of NM is disabled!")
            logging.warning("=============================================")
            slave_desc["nm_running"] = True
        else:
            slave_desc["nm_running"] = False

        k_release, _ = exec_cmd("uname -r", False, False, False)
        r_release, _ = exec_cmd("cat /etc/redhat-release", False, False, False)
        slave_desc["kernel_release"] = k_release.strip()
        slave_desc["redhat_release"] = r_release.strip()
        slave_desc["lnst_version"] = lnst_config.version

        return ("hello", slave_desc)

    def bye(self):
        self.restore_system_config()
        self.clear_resource_table()
        self._cache.del_old_entries()
        self.reset_file_transfers()
        self._remove_capture_files()
        return "bye"

    def kill_cmds(self):
        logging.info("Killing all forked processes.")
        self._command_context.cleanup()
        return "Commands killed"

    def map_if_by_hwaddr(self, if_id, hwaddr):
        devices = self.map_if_by_params(if_id, {'hwaddr' : hwaddr})

        return devices

    def map_if_by_params(self, if_id, params):
        devices = self.get_devices_by_params(params)

        if len(devices) == 1:
            dev = self._if_manager.get_device_by_params(params)
            self._if_manager.map_if(if_id, dev.get_if_index())

        return devices

    def unmap_if(self, if_id):
        self._if_manager.unmap_if(if_id)
        return True

    def get_devices(self):
        self._if_manager.rescan_devices()
        devices = self._if_manager.get_devices()
        result = {}
        for device in devices:
            result[device._if_index] = device.get_if_data()
        return result

    def get_device(self, if_index):
        self._if_manager.rescan_devices()
        device = self._if_manager.get_device(if_index)
        if device:
            return device.get_if_data()
        else:
            return {}

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

    def get_devices_by_params(self, params):
        devices = self._if_manager.get_devices()
        matched = []
        for dev in devices:
            dev_data = dev.get_if_data()
            entry = {"name": dev.get_name(),
                     "hwaddr": dev.get_hwaddr()}
            for key, value in params.iteritems():
                if key not in dev_data or dev_data[key] != value:
                    entry = None
                    break

            if entry is not None:
                matched.append(entry)

        return matched

    def get_if_data(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is None:
            return {}
        return dev.get_if_data()

    def link_cpu_ifstat(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is None:
            logging.error("Device with id '%s' not found." % if_id)
            return {}
        return dev.link_cpu_ifstat()

    def link_stats(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is None:
            logging.error("Device with id '%s' not found." % if_id)
            return {}
        return dev.link_stats()

    def set_addresses(self, if_id, ips):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is None:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        dev.set_addresses(ips)
        return True

    def add_route(self, if_id, dest, ipv6):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is None:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        dev.add_route(dest, ipv6)
        return True

    def del_route(self, if_id, dest, ipv6):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is None:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        dev.del_route(dest, ipv6)
        return True

    def add_nhs_route(self, if_id, dest, nhs, ipv6):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is None:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        dev.add_nhs_route(dest, nhs, ipv6)
        return True

    def del_nhs_route(self, if_id, dest, nhs, ipv6):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is None:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        dev.del_nhs_route(dest, nhs, ipv6)
        return True

    def set_device_up(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        dev.up()
        return True

    def set_device_down(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is not None:
            dev.down()
        else:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        return True

    def device_address_setup(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        dev.address_setup()
        return True

    def device_address_cleanup(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is not None:
            dev.address_cleanup()
        else:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        return True

    def set_link_up(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is not None:
            dev.link_up()
        else:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        return True

    def set_link_down(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is not None:
            dev.link_down()
        else:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        return True

    def set_unmapped_device_down(self, hwaddr):
        dev = self._if_manager.get_device_by_hwaddr(hwaddr)
        if dev is not None:
            dev.down()
        else:
            logging.warning("Device with hwaddr '%s' not found." % hwaddr)
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
        if device is not None:
            device.clear_configuration()
        else:
            logging.error("No device with id '%s' to deconfigure." % if_id)
        return True

    def start_packet_capture(self, filt):
        if not is_installed("tcpdump"):
            raise Exception("Can't start packet capture, tcpdump not available")

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

    def get_remaining_time(self, bg_id):
        cmd = self._command_context.get_cmd(bg_id)
        if "timeout" in cmd._command:
            cmd_timeout = cmd._command["timeout"]
        else:
            cmd_timeout = DEFAULT_TIMEOUT

        start_time = cmd._start_time
        current_time = time()

        remaining = cmd_timeout - (current_time - start_time)
        if remaining < 0:
            remaining = 0

        return int(remaining)

    def run_command(self, command):
        cmd = NetTestCommand(self._command_context, command,
                                    self._resource_table, self._log_ctl)

        if self._command_context.get_cmd(cmd.get_id()) != None:
            prev_cmd = self._command_context.get_cmd(cmd.get_id())
            if not prev_cmd.get_result_sent():
                if cmd.get_id() is None:
                    raise Exception("Previous foreground command still "\
                                    "running!")
                else:
                    raise Exception("Different command with id '%s' "\
                                    "still running!" % cmd.get_id())
            else:
                self._command_context.del_cmd(cmd)
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
        if cmd is not None:
            if not cmd.get_result_sent():
                cmd.kill(None)
                result = cmd.get_result()
                cmd.set_result_sent()
                return result
            else:
                pass
        else:
            raise Exception("No command with id '%s'." % id)

    def machine_cleanup(self):
        logging.info("Performing machine cleanup.")
        self._command_context.cleanup()

        for mroute_soc in self.mroute_sockets.values():
            mroute_soc.close()
            del mroute_soc
        self.mroute_sockets = {}

        self.restore_system_config()

        devs = self._if_manager.get_mapped_devices()
        for if_id, dev in devs.iteritems():
            peer = dev.get_peer()
            if peer == None:
                dev.clear_configuration()
            else:
                peer_if_index = peer.get_if_index()
                peer_id = self._if_manager.get_id_by_if_index(peer_if_index)
                self.deconfigure_if_pair(if_id, peer_id)

        self._if_manager.deconfigure_all()

        for netns in self._net_namespaces.keys():
            self.del_namespace(netns)
        self._net_namespaces = {}

        self._if_manager.clear_if_mapping()
        self._cache.del_old_entries()
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
                result = self._slave_server.wait_for_result(netns)
                return result["result"]
            elif pid == 0:
                self._slave_server.set_netns_sighandlers()
                #create new network namespace
                libc_name = ctypes.util.find_library("c")
                #from sched.h
                CLONE_NEWNET = 0x40000000
                CLONE_NEWNS = 0x00020000
                #based on ipnetns.c from the iproute2 project
                MNT_DETACH = 0x00000002
                MS_BIND = 4096
                MS_SLAVE = 1<<19
                MS_REC = 16384
                libc = ctypes.CDLL(libc_name)

                #based on ipnetns.c from the iproute2 project
                #bind to named namespace
                netns_path = "/var/run/netns/"
                if not os.path.exists(netns_path):
                    os.mkdir(netns_path, stat.S_IRWXU | stat.S_IRGRP |
                                         stat.S_IXGRP | stat.S_IROTH |
                                         stat.S_IXOTH)
                netns_path = netns_path + netns
                f = os.open(netns_path, os.O_RDONLY | os.O_CREAT | os.O_EXCL, 0)
                os.close(f)
                libc.unshare(CLONE_NEWNET)
                libc.mount("/proc/self/ns/net", netns_path, "none", MS_BIND, 0)

                #map network sysfs to new net
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
                self._if_manager.clear_if_mapping()
                self._server_handler.add_connection('netlink',
                                            self._if_manager.get_nl_socket())

                self._server_handler.set_netns(netns)
                self._server_handler.set_ctl_sock((write_pipe, "root_netns"))

                self._log_ctl.disable_logging()
                self._log_ctl.set_origin_name(netns)
                self._log_ctl.set_connection(write_pipe)

                logging.debug("Created network namespace %s" % netns)
                return True
            else:
                raise Exception("Fork failed!")

    def del_namespace(self, netns):
        if netns not in self._net_namespaces:
            logging.debug("Network namespace %s doesn't exist." % netns)
            return False
        else:
            MNT_DETACH = 0x00000002
            libc_name = ctypes.util.find_library("c")
            libc = ctypes.CDLL(libc_name)
            netns_path = "/var/run/netns/" + netns

            netns_pid = self._net_namespaces[netns]["pid"]
            os.kill(netns_pid, signal.SIGUSR1)
            os.waitpid(netns_pid, 0)

            # Remove named namespace
            try:
                libc.umount2(netns_path, MNT_DETACH)
                os.unlink(netns_path)
            except:
                logging.warning("Unable to remove named namespace %s." % netns_path)

            logging.debug("Network namespace %s removed." % netns)

            self._net_namespaces[netns]["pipe"].close()
            self._server_handler.del_netns(netns)
            del self._net_namespaces[netns]
            return True

    def get_routes(self, route_filter):
        try:
            route_output, _ = exec_cmd("ip route show %s" % route_filter)
        except:
            return {}

        dc_routes = []
        nh_routes = []
        ip_re = "\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        ip6_re = "(?:(?:[\da-f]{1,4}:)*|:)(?::|(?:[\da-f]{1,4})|(?::[\da-f]{1,4})*)"
        prefix_re = "^((?:local )?" + "(?:%s|%s)" % (ip_re, ip6_re) + "(?:/\d{1,3})?)"

        # parse directly connected routes
        dc_route_re = prefix_re + " dev (\w+) (.*)"
        dc_matchs = re.findall(dc_route_re, route_output, re.M)

        for dc_match in dc_matchs:
            dc_route = { "prefix" : dc_match[0],
                         "dev"    : dc_match[1],
                         "flags"  : dc_match[2] }
            dc_routes.append(dc_route)

        # parse nexthop routes
        nh_re = " via (" + ip_re + ").*dev (\w+) (.*)"
        nh_route_re = prefix_re + nh_re
        nh_route_matchs = re.findall(nh_route_re, route_output, re.M)

        for nh_route_match in nh_route_matchs:
            nexthop = { "ip" : nh_route_match[1],
                        "dev" : nh_route_match[2],
                        "flags" : nh_route_match[3]}
            nh_route = {"prefix"  : nh_route_match[0],
                        "nexthops": [ nexthop ],
                        "flags" : ""}
            nh_routes.append(nh_route)

        # parse ECMP routes
        ecmp_route_re = prefix_re + "(.*)\n((?:.*nexthop .*\n?)+)"
        ecmp_matchs = re.findall(ecmp_route_re, route_output, re.M)

        for ecmp_match in ecmp_matchs:
            # parse each nexthop
            nexthops = []
            nh_matchs = re.findall(nh_re, ecmp_match[2])

            for nh_match in nh_matchs:
                nexthop = { "ip" : nh_match[0],
                            "dev" : nh_match[1],
                            "flags" : nh_match[2]}
                nexthops.append(nexthop)

            ecmp_route = {"prefix"  : ecmp_match[0],
                          "nexthops": nexthops,
                          "flags"   : ecmp_match[1] }
            nh_routes.append(ecmp_route)

        return dc_routes, nh_routes

    def set_if_netns(self, if_id, netns):
        netns_pid = self._net_namespaces[netns]["pid"]

        device = self._if_manager.get_mapped_device(if_id)
        dev_name = device.get_name()
        device.set_netns(netns)
        hwaddr = device.get_hwaddr()

        exec_cmd("ip link set %s netns %d" % (dev_name, netns_pid))
        msg = {"type": "command", "method_name": "map_if_by_hwaddr",
               "args": [if_id, hwaddr]}
        self._server_handler.send_data_to_netns(netns, msg)
        result = self._slave_server.wait_for_result(netns)
        return result

    def return_if_netns(self, if_id):
        device = self._if_manager.get_mapped_device(if_id)
        if device.get_netns() == None:
            dev_name = device.get_name()
            ppid = os.getppid()
            exec_cmd("ip link set %s netns %d" % (dev_name, ppid))
            self._if_manager.unmap_if(if_id)
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

    def add_br_vlan(self, if_id, br_vlan_info):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        brt.add_vlan(br_vlan_info)
        return True

    def del_br_vlan(self, if_id, br_vlan_info):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        brt.del_vlan(br_vlan_info)
        return True

    def get_br_vlans(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        return brt.get_vlans()

    def add_br_fdb(self, if_id, br_fdb_info):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        brt.add_fdb(br_fdb_info)
        return True

    def del_br_fdb(self, if_id, br_fdb_info):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        brt.del_fdb(br_fdb_info)
        return True

    def get_br_fdbs(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        return brt.get_fdbs()

    def set_br_learning(self, if_id, br_learning_info):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        brt.set_learning(br_learning_info)
        return True

    def set_br_learning_sync(self, if_id, br_learning_sync_info):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        brt.set_learning_sync(br_learning_sync_info)
        return True

    def set_br_flooding(self, if_id, br_flooding_info):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        brt.set_flooding(br_flooding_info)
        return True

    def set_br_state(self, if_id, br_state_info):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        brt.set_state(br_state_info)
        return True

    def set_br_mcast_snooping(self, if_id, set_on = True):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        brt.set_mcast_snooping(set_on)
        return True

    def set_br_mcast_querier(self, if_id, set_on = True):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        brt.set_mcast_querier(set_on)
        return True

    def set_speed(self, if_id, speed):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is not None:
            dev.set_speed(speed)
        else:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        return True

    def set_autoneg(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is not None:
            dev.set_autoneg()
        else:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        return True

    def wait_interface_init(self):
        self._if_manager.wait_interface_init()
        return True

    def slave_add(self, if_id, slave_id):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is not None:
            dev.slave_add(slave_id)
        else:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        return True

    def slave_del(self, if_id, slave_id):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is not None:
            dev.slave_del(slave_id)
        else:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        return True

    def _is_systemd(self):
        stdout, _ = exec_cmd("pidof systemd", die_on_err=False)
        return len(stdout) != 0

    def _configure_service(self, service, action):
        if self._is_systemd():
            exec_cmd("systemctl {} {}".format(action, service))
        else:
            exec_cmd("service {} {}".format(service, action))
        return True

    def enable_service(self, service):
        return self._configure_service(service, "start")

    def disable_service(self, service):
        return self._configure_service(service, "stop")

    def restart_service(self, service):
        return self._configure_service(service, "restart")

    def get_num_cpus(self):
        return int(os.sysconf('SC_NPROCESSORS_ONLN'))

    def get_ethtool_stats(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        return dev.get_ethtool_stats()

    def enable_lldp(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        dev.enable_lldp()
        return True

    def set_pause_on(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is not None:
            dev.set_pause_on()
        else:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        return True

    def set_pause_off(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is not None:
            dev.set_pause_off()
        else:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        return True

    def set_mcast_flood(self, if_id, on):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is not None:
            dev.set_mcast_flood(on)
        else:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        return True

    def set_mcast_router(self, if_id, state):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is not None:
            dev.set_mcast_router(state)
        else:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        return True

    def mroute_operation(self, op_type, op, table_id):
        if not self.mroute_sockets.has_key(table_id):
            logging.error("mroute %s table was not init", table_id)
            return False
        try:
            self.mroute_sockets[table_id].setsockopt(socket.IPPROTO_IP,
                                                     op_type, op)
        except Exception as e:
           raise Exception("mroute operation failed")
        return True

    def mroute_init(self, table_id):
        logging.debug("Initializing mroute socket")
        if not self.mroute_sockets.has_key(table_id):
            self.mroute_sockets[table_id] = socket.socket(socket.AF_INET,
                                                          socket.SOCK_RAW,
                                                          socket.IPPROTO_IGMP)
        self.mroute_sockets[table_id].settimeout(0.5)
        init_struct = struct.pack("I", MROUTE.INIT)
        res = self.mroute_operation(MROUTE.INIT, init_struct, table_id)
        return res

    def mroute_finish(self, table_id):
        logging.debug("Closing mroute socket")
        finish_struct = struct.pack("I", MROUTE.FINISH)
        res = self.mroute_operation(MROUTE.FINISH, finish_struct, table_id)
        return res

    def mroute_pim_init(self, table_id, pim_stop=False):
        logging.debug("Initializing mroute PIM")
        pim_struct = struct.pack("I", not pim_stop)
        return self.mroute_operation(MROUTE.PIM_INIT, pim_struct, table_id)

    def mroute_table(self, index):
        logging.debug("Creating mroute table %d" % index)

        self.mroute_sockets[index] = socket.socket(socket.AF_INET,
                                                   socket.SOCK_RAW,
                                                   socket.IPPROTO_IGMP)
        table_struct = struct.pack("I", index)
        return self.mroute_operation(MROUTE.TABLE, table_struct, index)

    def mroute_add_vif(self, if_id, vif_id, table_id):
        logging.debug("Adding mroute VIF index %d" % vif_id)

        dev = self._if_manager.get_mapped_device(if_id)
        if dev is None:
            logging.error("Device with id '%s' not found." % if_id)
            return False

        if_index = dev.get_if_index()
        vif_struct = struct.pack("HBBIII", vif_id, MROUTE.USE_IF_INDEX,
                                 MROUTE.DEFAULT_TTL, 0, if_index, 0)
        return self.mroute_operation(MROUTE.VIF_ADD, vif_struct, table_id)

    def mroute_del_vif(self, if_id, vif_id, table_id):
        logging.debug("Deleting mroute VIF index %d" % vif_id)
        vif_struct = struct.pack("HBBIII", vif_id, 0,0, 0, 0, 0)
        return self.mroute_operation(MROUTE.VIF_DEL, vif_struct, table_id)

    def mroute_add_vif_reg(self, vif_id, table_id):
        logging.debug("Adding mroute pimreg VIF with index %d" % vif_id)
        vif_struct = struct.pack("HBBIII", vif_id, MROUTE.REGISET_VIF,
                                 MROUTE.DEFAULT_TTL, 0, 0, 0)
        return self.mroute_operation(MROUTE.VIF_ADD, vif_struct, table_id)

    def mroute_add_mfc(self, source, group, source_vif, out_vifs,
                       table_id, proxi = False):
        logging.debug("Adding mroute MFC route (%s, %s) -> %s" %
                      (source, group, str(out_vifs)))

        ttls = [0] * MROUTE.MAX_VIF
        for vif, ttl in out_vifs.items():
            if vif >= MROUTE.MAX_VIF:
                logging.error("ilegal VIF was asked")
                return False
            ttls[vif] = ttl

        mfc_struct = socket.inet_aton(source) + socket.inet_aton(group) + \
                     struct.pack("H32B", source_vif, *ttls) + \
                     struct.pack("IIIIH", 0,0,0,0,0)

        op_type = MROUTE.MFC_ADD if not proxi else MROUTE.MFC_ADD_PROXI
        return self.mroute_operation(op_type, mfc_struct, table_id)

    def mroute_del_mfc(self, source, group, source_vif, table_id,
                       proxi = False):
        logging.debug("Deleting mroute MFC route (%s, %s)" % (source, group))

        ttls = [0] * MROUTE.MAX_VIF
        mfc_struct = socket.inet_aton(source) + socket.inet_aton(group) + \
                     struct.pack("H32B", source_vif, *ttls) + \
                     struct.pack("IIIIH",0, 0,0,0,0)

        op_type = MROUTE.MFC_DEL if not proxi else MROUTE.MFC_DEL_PROXI
        return self.mroute_operation(op_type, mfc_struct, table_id)

    def mroute_get_notif(self, table_id):
        if not self.mroute_sockets.has_key(table_id):
            logging.error("mroute table %s was not init", table_id)
            return False
        try:
            notif = self.mroute_sockets[table_id].recv(65*1024)
        except:
            return {}

        if len(notif) < 28:
            raise Exception("notif of wrong size was capture")

        notif_type, zero, source_vif = struct.unpack("BBB", notif[8:11])
        res = {}
        if zero != 0:
            res = {"error": True}
        res["notif_type"] = notif_type
        res["source_vif"] = source_vif
        res["source_ip"] = socket.inet_ntoa(notif[12:16])
        res["group_ip"] = socket.inet_ntoa(notif[16:20])
        res["raw"] = notif
        res["data"] = notif[28:]
        return res

    def get_coalesce(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is not None:
            return dev.get_coalesce()
        else:
            logging.error("Device with id '%s' not found." % if_id)
            return None

    def set_coalesce(self, if_id, cdata):
        dev = self._if_manager.get_mapped_device(if_id)
        if dev is not None:
            dev.set_coalesce(cdata)
            return True
        else:
            logging.error("Device with id '%s' not found." % if_id)
            return False

class ServerHandler(ConnectionHandler):
    def __init__(self, addr):
        super(ServerHandler, self).__init__()
        self._netns_con_mapping = {}
        try:
            self._s_socket = socket.socket()
            self._s_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._s_socket.bind(addr)
            self._s_socket.listen(1)
        except socket.error as e:
            logging.error(e[1])
            exit(1)

        self._netns = None
        self._c_socket = None

        self._if_manager = None

        self._security = lnst_config.get_section_values("security")

    def set_if_manager(self, if_manager):
        self._if_manager = if_manager

    def accept_connection(self):
        self._c_socket, addr = self._s_socket.accept()
        self._c_socket = (SlaveSecSocket(self._c_socket), addr[0])
        logging.info("Recieved connection from %s" % self._c_socket[1])

        try:
            self._c_socket[0].handshake(self._security)
        except:
            self.close_c_sock()
            raise

        self.add_connection(self._c_socket[1], self._c_socket[0])
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
        self.add_connection(self._c_socket[1], self._c_socket[0])

    def close_s_sock(self):
        self._s_socket.close()
        self._s_socket = None

    def close_c_sock(self):
        self._c_socket[0].close()
        self.remove_connection(self._c_socket[0])
        self._c_socket = None

    def check_connections(self):
        msgs = super(ServerHandler, self).check_connections()
        if 'netlink' not in self._connection_mapping:
            self._if_manager.reconnect_netlink()
            self.add_connection('netlink', self._if_manager.get_nl_socket())
        return msgs

    def get_messages(self):
        messages = self.check_connections()

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
        if self.get_connection(addr) == None:
            logging.info("Lost controller connection.")
            self._c_socket = None
        return messages

    def get_messages_from_con(self, con_id):
        if con_id in self._connection_mapping:
            connection = self._connection_mapping[con_id]
        elif con_id in self._netns_con_mapping:
            connection = self._netns_con_mapping[con_id]
        else:
            raise Exception("Unknown connection id '%s'." % con_id)
        return self._check_connections([connection])

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
        if netns not in self._netns_con_mapping:
            raise Exception("No network namespace '%s'!" % netns)
        else:
            netns_con = self._netns_con_mapping[netns]
            return send_data(netns_con, data)

    def clear_connections(self):
        super(ServerHandler, self).clear_connections()
        self._netns_con_mapping = {}

    def update_connections(self, connections):
        for key, connection in connections.iteritems():
            self.remove_connection_by_id(key)
            self.add_connection(key, connection)

    def set_netns(self, netns):
        self._netns = netns

    def add_netns(self, netns, connection):
        self._connections.append(connection)
        self._netns_con_mapping[netns] = connection

    def del_netns(self, netns):
        if netns in self._netns_con_mapping:
            connection = self._netns_con_mapping[netns]
            self._connections.remove(connection)
            del self._netns_con_mapping[netns]

    def clear_netns_connections(self):
        for netns, con in self._netns_con_mapping:
            self._connections.remove(con)
        self._netns_con_mapping = {}

class NetTestSlave:
    def __init__(self, log_ctl):
        die_when_parent_die()

        self._cmd_context = NetTestCommandContext()
        port = lnst_config.get_option("environment", "rpcport")
        logging.info("Using RPC port %d." % port)
        self._server_handler = ServerHandler(("", port))
        self._if_manager = InterfaceManager(self._server_handler)

        self._server_handler.set_if_manager(self._if_manager)

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
                except (socket.error, SecSocketException):
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
                cmd.set_result_sent()
            else:
                cmd = self._cmd_context.get_cmd(msg["cmd_id"])
                cmd.join()
                del msg["cmd_id"]

                cmd.set_result(msg["result"])
                if cmd.finished():
                    msg["result"] = cmd.get_result()
                    self._server_handler.send_data_to_ctl(msg)
                    cmd.set_result_sent()
        elif msg["type"] == "netlink":
            self._if_manager.handle_netlink_msgs(msg["data"])
        elif msg["type"] == "from_netns":
            self._server_handler.send_data_to_ctl(msg["data"])
        elif msg["type"] == "to_netns":
            netns = msg["netns"]
            try:
                self._server_handler.send_data_to_netns(netns, msg["data"])
            except:
                log_exc_traceback()
                type, value, tb = sys.exc_info()
                exc_trace = ''.join(traceback.format_exception(type,
					   value, tb))
                response = {"type": "exception", "Exception": value}

                self._server_handler.send_data_to_ctl(response)
                return
        else:
            raise Exception("Recieved unknown command")

        pipes = self._cmd_context.get_read_pipes()
        self._server_handler.update_connections(pipes)

    def register_die_signal(self, signum):
        signal.signal(signum, self._signal_die_handler)

    def _signal_die_handler(self, signum, frame):
        logging.info("Caught signal %d -> dying" % signum)
        self._finished = True

    def _parent_resend_signal_handler(self, signum, frame):
        logging.info("Caught signal %d -> resending to parent" % signum)
        os.kill(os.getppid(), signum)

    def set_netns_sighandlers(self):
        signal.signal(signal.SIGHUP, self._parent_resend_signal_handler)
        signal.signal(signal.SIGINT, self._parent_resend_signal_handler)
        signal.signal(signal.SIGTERM, self._parent_resend_signal_handler)
        signal.signal(signal.SIGUSR1, self._signal_die_handler)
