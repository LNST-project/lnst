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
import cPickle
import tempfile
import imp
import copy
from time import sleep
from xmlrpclib import Binary
from lnst.Common.NetUtils import MacPool
from lnst.Common.Utils import wait_for, md5sum, dir_md5sum, create_tar_archive
from lnst.Common.Utils import check_process_running, bool_it, get_module_tools
from lnst.Common.NetTestCommand import NetTestCommandContext, NetTestCommand
from lnst.Common.NetTestCommand import str_command, CommandException
from lnst.Controller.RecipeParser import RecipeParser, RecipeError
from lnst.Controller.SlavePool import SlavePool
from lnst.Controller.Machine import Machine, MachineError, VirtualInterface
from lnst.Common.ConnectionHandler import send_data, recv_data
from lnst.Common.ConnectionHandler import ConnectionHandler
from lnst.Common.Config import lnst_config
from lnst.Common.RecipePath import RecipePath
from lnst.Common.Colours import decorate_with_preset
from lnst.Common.NetUtils import test_tcp_connection
import lnst.Controller.Task as Task

# conditional support for libvirt
if check_process_running("libvirtd"):
    from lnst.Controller.VirtUtils import VirtNetCtl, VirtDomainCtl

class NetTestError(Exception):
    pass

def ignore_event(**kwarg):
    pass

class NetTestController:
    def __init__(self, recipe_path, log_ctl,
                 res_serializer=None, pool_checks=True,
                 defined_aliases=None, overriden_aliases=None,
                 reduce_sync=False):
        self._res_serializer = res_serializer
        self._remote_capture_files = {}
        self._log_ctl = log_ctl
        self._recipe_path = recipe_path
        self._msg_dispatcher = MessageDispatcher(log_ctl)
        self._reduce_sync = reduce_sync
        self._parser = RecipeParser(recipe_path)

        self.remove_saved_machine_config()

        sp = SlavePool(lnst_config.get_option('environment', 'pool_dirs'),
                       check_process_running("libvirtd"), pool_checks)
        self._slave_pool = sp

        self._machines = {}
        self._network_bridges = {}
        self._tasks = []

        mac_pool_range = lnst_config.get_option('environment', 'mac_pool_range')
        self._mac_pool = MacPool(mac_pool_range[0], mac_pool_range[1])

        self._parser.set_machines(self._machines)
        self._parser.set_aliases(defined_aliases, overriden_aliases)
        self._recipe = self._parser.parse()

        modules_dirs = lnst_config.get_option('environment', 'module_dirs')
        tools_dirs = lnst_config.get_option('environment', 'tool_dirs')

        self._resource_table = {}
        self._resource_table["module"] = self._load_test_modules(modules_dirs)
        self._resource_table["tools"] = self._load_test_tools(tools_dirs)

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

    def _get_machine_requirements(self):
        recipe = self._recipe

        # There must be some machines specified in the recipe
        if "machines" not in recipe or \
          ("machines" in recipe and len(recipe["machines"]) == 0):
            msg = "No hosts specified in the recipe. At least two " \
                  "hosts are required to perform a network test."
            raise RecipeError(msg, recipe)

        # machine requirements
        mreq = {}
        for machine in recipe["machines"]:
            m_id = machine["id"]

            if m_id in mreq:
                msg = "Machine with id='%s' already exists." % m_id
                raise RecipeError(msg, machine)

            params = {}
            if "params" in machine:
                for p in machine["params"]:
                    if p["name"] in params:
                        msg = "Parameter '%s' of host %s was specified " \
                              "multiple times. Overriding the previous value." \
                              % (p["name"], m_id)
                        logging.warn(RecipeError(msg, p))
                    name = p["name"]
                    val = p["value"]
                    params[name] = val

            # Each machine must have at least one interface
            if "interfaces" not in machine or \
              ("interfaces" in machine and len(machine["interfaces"]) == 0):
                msg = "Hot '%s' has no interfaces specified." % m_id
                raise RecipeError(msg, machine)

            ifaces = {}
            for iface in machine["interfaces"]:
                if_id = iface["id"]
                if if_id in ifaces:
                    msg = "Interface with id='%s' already exists on host " \
                          "'%s'." % (if_id, m_id)

                iface_type = iface["type"]
                if iface_type != "eth":
                    continue

                iface_params = {}
                if "params" in iface:
                    for i in iface["params"]:
                        if i["name"] in iface_params:
                            msg = "Parameter '%s' of interface %s of " \
                                  "host %s was defined multiple times. " \
                                  "Overriding the previous value." \
                                  % (i["name"], if_id, m_id)
                            logging.warn(RecipeError(msg, p))
                        name = i["name"]
                        val = i["value"]
                        iface_params[name] = val

                ifaces[if_id] = {
                    "network": iface["network"],
                    "params": iface_params
                }

            mreq[m_id] = {"params": params, "interfaces": ifaces}

        return mreq

    def _prepare_network(self, resource_sync=True):
        recipe = self._recipe

        machines = self._machines
        for m_id in machines.keys():
            self._prepare_machine(m_id, resource_sync)

        for machine_xml_data in recipe["machines"]:
            m_id = machine_xml_data["id"]
            for iface_xml_data in machine_xml_data["interfaces"]:
                self._prepare_interface(m_id, iface_xml_data)

            ifaces = machines[m_id].get_ordered_interfaces()
            for iface in ifaces:
                iface.configure()
            for iface in ifaces:
                iface.up()

    def _prepare_provisioning(self):
        mreq = self._get_machine_requirements()
        sp = self._slave_pool
        machines = self._machines
        if not sp.provision_machines(mreq, machines):
            msg = "This setup cannot be provisioned with the current pool."
            raise NetTestError(msg)

        if sp.is_setup_virtual() and os.geteuid() != 0:
            msg = "Provisioning this setup requires additional configuration "\
                  "of the virtual hosts in the pool. LNST needs root "\
                  "priviledges so it can connect to qemu."
            raise NetTestError(msg)

        logging.info("Provisioning initialized")
        for m_id in machines.keys():
            provisioner = sp.get_provisioner_id(m_id)
            logging.info("  host %s uses %s" % (m_id, provisioner))

    def _prepare_machine(self, m_id, resource_sync=True):
        machine = self._machines[m_id]
        address = socket.gethostbyname(machine.get_hostname())

        self._log_ctl.add_slave(m_id)
        machine.set_rpc(self._msg_dispatcher)
        machine.set_mac_pool(self._mac_pool)
        machine.set_network_bridges(self._network_bridges)

        recipe_name = os.path.basename(self._recipe_path)
        machine.configure(recipe_name)

        sync_table = {'module': {}, 'tools': {}}
        if resource_sync:
            for task in self._recipe['tasks']:
                res_table = copy.deepcopy(self._resource_table)
                if 'module_dir' in task:
                    modules = self._load_test_modules([task['module_dir']])
                    res_table['module'].update(modules)
                if 'tools_dir' in task:
                    tools = self._load_test_tools([task['tools_dir']])
                    res_table['tools'].update(tools)

                if 'commands' not in task:
                    if not self._reduce_sync:
                        sync_table = res_table
                        break
                    else:
                        continue
                for cmd in task['commands']:
                    if 'host' not in cmd or cmd['host'] != m_id:
                        continue
                    if cmd['type'] == 'test':
                        mod = cmd['module']
                        if mod in res_table['module']:
                            sync_table['module'][mod] = res_table['module'][mod]
                            # check if test module uses some test tools
                            mod_path = res_table['module'][mod]["path"]
                            mod_tools = get_module_tools(mod_path)
                            for t in mod_tools:
                                 if t in sync_table['tools']:
                                     continue
                                 logging.debug("Adding '%s' tool as dependency\
                                     of %s test module" % (t, mod))
                                 sync_table['tools'][t] = res_table['tools'][t]
                        else:
                            msg = "Module '%s' not found on the controller"\
                                    % mod
                            raise RecipeError(msg, cmd)
                    if cmd['type'] == 'exec' and 'from' in cmd:
                        tool = cmd['from']
                        if tool in res_table['tools']:
                            sync_table['tools'][tool] = res_table['tools'][tool]
                        else:
                            msg = "Tool '%s' not found on the controller" % tool
                            raise RecipeError(msg, cmd)
        machine.sync_resources(sync_table)

    def _prepare_interface(self, m_id, iface_xml_data):
        machine = self._machines[m_id]
        if_id = iface_xml_data["id"]
        if_type = iface_xml_data["type"]

        try:
            iface = machine.get_interface(if_id)
        except MachineError:
            iface = machine.new_soft_interface(if_id, if_type)

        if "slaves" in iface_xml_data:
            for slave in iface_xml_data["slaves"]:
                slave_id = slave["id"]
                iface.add_slave(machine.get_interface(slave_id))

                # Some soft devices (such as team) use per-slave options
                if "options" in slave:
                    for opt in slave["options"]:
                        iface.set_slave_option(slave_id, opt["name"],
                                               opt["value"])

        if "addresses" in iface_xml_data:
            for addr in iface_xml_data["addresses"]:
                iface.add_address(addr)

        if "options" in iface_xml_data:
            for opt in iface_xml_data["options"]:
                iface.set_option(opt["name"], opt["value"])

        if "ovs_conf" in iface_xml_data:
            iface.set_ovs_conf(iface_xml_data["ovs_conf"])

    def _prepare_tasks(self):
        self._tasks = []
        for task_data in self._recipe["tasks"]:
            task = {}
            task["quit_on_fail"] = False
            if "quit_on_fail" in task_data:
                task["quit_on_fail"] = bool_it(task_data["quit_on_fail"])

            if "module_dir" in task_data:
                task["module_dir"] = task_data["module_dir"]

            if "tools_dir" in task_data:
                task["tools_dir"] = task_data["tools_dir"]

            if "python" in task_data:
                root = RecipePath(None, self._recipe_path).get_root()
                path = RecipePath(root, task_data["python"])

                task["python"] = path
                if not path.exists():
                    msg = "Task file '%s' not found." % path
                    raise RecipeError(msg, task_data)

                self._tasks.append(task)
                continue

            task["commands"] = task_data["commands"]
            task["skeleton"] = []
            for cmd_data in task["commands"]:
                cmd = {"type": cmd_data["type"]}

                if "host" in cmd_data:
                    cmd["host"] = cmd_data["host"]
                    if cmd["host"] not in self._machines:
                        msg = "Invalid host id '%s'." % cmd["host"]
                        raise RecipeError(msg, cmd_data)

                if cmd["type"] in ["test", "exec"]:
                    if "bg_id" in cmd_data:
                        cmd["bg_id"] = cmd_data["bg_id"]
                elif cmd["type"] in ["wait", "intr", "kill"]:
                    cmd["proc_id"] = cmd_data["bg_id"]

                task["skeleton"].append(cmd)

            if self._check_task(task):
                raise RecipeError("Incorrect command sequence.", task_data)

            self._tasks.append(task)

    def _prepare_command(self, cmd_data):
        cmd = {"type": cmd_data["type"]}
        if "host" in cmd_data:
            cmd["host"] = cmd_data["host"]
            if cmd["host"] not in self._machines:
                msg = "Invalid host id '%s'." % cmd["host"]
                raise RecipeError(msg, cmd_data)

        if "expect" in cmd_data:
            expect = cmd_data["expect"]
            if expect not in ["pass", "fail"]:
                msg = "Illegal expect attribute value."
                raise RecipeError(msg, cmd_data)
            cmd["expect"] = expect == "pass"

        if cmd["type"] == "test":
            cmd["module"] = cmd_data["module"]

            cmd_opts = {}
            if "options" in cmd_data:
                for opt in cmd_data["options"]:
                    name = opt["name"]
                    val = opt["value"]

                    if name not in cmd_opts:
                        cmd_opts[name] = []

                    cmd_opts[name].append({"value": val})
            cmd["options"] = cmd_opts
        elif cmd["type"] == "exec":
            cmd["command"] = cmd_data["command"]

            if "from" in cmd_data:
                cmd["from"] = cmd_data["from"]
        elif cmd["type"] in ["wait", "intr", "kill"]:
            # XXX The internal name (proc_id) is different, because
            # bg_id is already used by LNST in a different context
            cmd["proc_id"] = cmd_data["bg_id"]
        elif cmd["type"] == "config":
            cmd["persistent"] = False
            if "persistent" in cmd_data:
                cmd["persistent"] = bool_it(cmd_data["persistent"])

            cmd["options"] = []
            for opt in cmd_data["options"]:
                name = opt["name"]
                value = opt["value"]
                cmd["options"].append({"name": name, "value": value})
        elif cmd["type"] == "ctl_wait":
            cmd["seconds"] = int(cmd_data["seconds"])
        else:
            msg = "Unknown command type '%s'" % cmd["type"]
            raise RecipeError(msg, cmd_data)


        if cmd["type"] in ["test", "exec"]:
            if "bg_id" in cmd_data:
                cmd["bg_id"] = cmd_data["bg_id"]

            if "timeout" in cmd_data:
                try:
                    cmd["timeout"] = int(cmd_data["timeout"])
                except ValueError:
                    msg = "Timeout value must be an integer."
                    raise RecipeError(msg, cmd_data)

        return cmd

    def _check_task(self, task):
        err = False
        bg_ids = {}
        for i, command in enumerate(task["skeleton"]):
            if command["type"] == "ctl_wait":
                continue

            machine_id = command["host"]
            if not machine_id in bg_ids:
                bg_ids[machine_id] = set()

            cmd_type = command["type"]
            if cmd_type in ["wait", "intr", "kill"]:
                bg_id = command["proc_id"]
                if bg_id in bg_ids[machine_id]:
                    bg_ids[machine_id].remove(bg_id)
                else:
                    logging.error("Found command \"%s\" for bg_id \"%s\" on "
                              "host \"%s\" which was not previously "
                              "defined", cmd_type, bg_id, machine_id)
                    err = True

            if "bg_id" in command:
                bg_id = command["bg_id"]
                if not bg_id in bg_ids[machine_id]:
                    bg_ids[machine_id].add(bg_id)
                else:
                    logging.error("Command \"%d\" uses bg_id \"%s\" on host"
                              "\"%s\" which is already used",
                                            i, bg_id, machine_id)
                    err = True

        for machine_id in bg_ids:
            for bg_id in bg_ids[machine_id]:
                logging.error("bg_id \"%s\" on host \"%s\" has no kill/wait "
                          "command to it", bg_id, machine_id)
                err = True

        return err

    def _cleanup_slaves(self, deconfigure=True):
        if self._machines == None:
            return

        for machine_id, machine in self._machines.iteritems():
            if machine.is_configured():
                try:
                    machine.cleanup(deconfigure)
                except:
                    pass

                #clean-up slave logger
                self._log_ctl.remove_slave(machine_id)

        # remove dynamically created bridges
        if deconfigure:
            for bridge in self._network_bridges.itervalues():
                bridge.cleanup()

    def _save_machine_config(self):
        #saves current virtual configuration to a file, after pickling it
        config_data = dict()
        machines = config_data["machines"] = {}
        for m in self._machines.itervalues():
            machine = machines[m.get_hostname()] = dict()

            if m.get_libvirt_domain() != None:
                machine["libvirt_dom"] = m.get_libvirt_domain()
            machine["interfaces"] = []

            for i in m._interfaces:
                if isinstance(i, VirtualInterface):
                    hwaddr = i.get_orig_hwaddr()

                    machine["interfaces"].append(hwaddr)

        config_data["bridges"] = bridges = []
        for bridge in self._network_bridges.itervalues():
            bridges.append(bridge.get_name())

        with open("/tmp/.lnst_machine_conf", "wb") as f:
            pickled_data = cPickle.dump(config_data, f)

    @classmethod
    def remove_saved_machine_config(cls):
        #removes previously saved configuration
        cfg = None
        try:
            with open("/tmp/.lnst_machine_conf", "rb") as f:
                cfg = cPickle.load(f)
        except:
            logging.info("No previous configuration found.")
            return

        if cfg:
            logging.info("Cleaning up leftover configuration from previous "\
                         "config_only run.")
            for hostname, machine in cfg["machines"].iteritems():
                port = lnst_config.get_option("environment", "rpcport")
                if test_tcp_connection(hostname, port):
                    rpc_con = socket.create_connection((hostname, port))

                    rpc_msg= {"type": "command",
                              "method_name": "machine_cleanup",
                              "args": []}

                    logging.debug("Calling cleanup on slave '%s'" % hostname)
                    send_data(rpc_con, rpc_msg)
                    while True:
                        msg = recv_data(rpc_con)
                        if msg['type'] == 'result':
                            break
                    rpc_con.close()

                if "libvirt_dom" in machine:
                    libvirt_dom = machine["libvirt_dom"]
                    domain_ctl = VirtDomainCtl(libvirt_dom)
                    logging.info("Detaching dynamically created interfaces.")
                    for i in machine["interfaces"]:
                        try:
                            domain_ctl.detach_interface(i)
                        except:
                            pass

            logging.info("Removing dynamically created bridges.")
            for br in cfg["bridges"]:
                try:
                    net_ctl = VirtNetCtl(br)
                    net_ctl.cleanup()
                except:
                    pass

            os.remove("/tmp/.lnst_machine_conf")

    def match_setup(self):
        self._prepare_provisioning()

        return {"passed": True}

    def config_only_recipe(self):
        try:
            self._prepare_provisioning()
            self._prepare_network(resource_sync=False)
        except (KeyboardInterrupt, Exception) as exc:
            msg = "Exception raised during configuration."
            logging.error(msg)
            self._cleanup_slaves()
            raise

        sp = self._slave_pool
        self._save_machine_config()

        self._cleanup_slaves(deconfigure=False)
        return {"passed": True}

    def run_recipe(self, packet_capture=False):
        try:
            self._prepare_provisioning()
            self._prepare_tasks()
            self._prepare_network()
        except (KeyboardInterrupt, Exception) as exc:
            msg = "Exception raised during configuration."
            logging.error(msg)
            self._cleanup_slaves()
            raise

        if packet_capture:
            self._start_packet_capture()

        err = None
        try:
            res = self._run_recipe()
        except Exception as exc:
            logging.error("Recipe execution terminated by unexpected exception")
            raise
        finally:
            if packet_capture:
                self._stop_packet_capture()
                self._gather_capture_files()
            self._cleanup_slaves()

        return res

    def _run_recipe(self):
        overall_res = {"passed": True}

        for task in self._tasks:
            self._res_serializer.add_task()
            try:
                res = self._run_task(task)
            except CommandException as exc:
                logging.debug(exc)
                overall_res["passed"] = False
                overall_res["err_msg"] = "Command exception raised."
                break

            for machine in self._machines.itervalues():
                machine.restore_system_config()

            # task failed, check if we should quit_on_fail
            if not res:
                overall_res["passed"] = False
                overall_res["err_msg"] = "At least one command failed."
                if task["quit_on_fail"]:
                    break

        return overall_res

    def _run_python_task(self, task):
        #backup of resource table
        res_table_bkp = copy.deepcopy(self._resource_table)
        if 'module_dir' in task:
            modules = self._load_test_modules([task['module_dir']])
            self._resource_table['module'].update(modules)
        if 'tools_dir' in task:
            tools = self._load_test_tools([task['tools_dir']])
            self._resource_table['tools'].update(tools)

        # Initialize the API handle
        Task.ctl = Task.ControllerAPI(self, self._machines)

        task_path = task["python"]
        name = os.path.basename(task_path.abs_path()).split(".")[0]
        module = imp.load_source(name, task_path.resolve())

        #restore resource table
        self._resource_table = res_table_bkp

        return module.ctl._result

    def _run_task(self, task):
        if "python" in task:
            return self._run_python_task(task)

        seq_passed = True
        for cmd_data in task["commands"]:
            cmd = self._prepare_command(cmd_data)
            cmd_res = self._run_command(cmd)
            if not cmd_res["passed"]:
                seq_passed = False

        return seq_passed

    def _run_command(self, command):
        logging.info("Executing command: [%s]", str_command(command))

        if "desc" in command:
            logging.info("Cmd description: %s", command["desc"])

        if command["type"] == "ctl_wait":
            sleep(command["seconds"])
            cmd_res = {"passed": True,
                       "res_header": "%-9s%ss" % ("ctl_wait",
                                                   command["seconds"]),
                       "msg": "",
                       "res_data": None}
            if self._res_serializer:
                self._res_serializer.add_cmd_result(command, cmd_res)
            return cmd_res

        machine_id = command["host"]
        machine = self._machines[machine_id]

        try:
            cmd_res = machine.run_command(command)
        except Exception as exc:
            cmd_res = {"passed": False,
                       "res_data": {"Exception": str(exc)},
                       "msg": "Exception raised.",
                       "res_header": "EXCEPTION",
                       "report": str(exc)}
            raise
        finally:
            if self._res_serializer:
                self._res_serializer.add_cmd_result(command, cmd_res)

        if cmd_res["passed"]:
            res_str = decorate_with_preset("PASS", "pass")
        else:
            res_str = decorate_with_preset("FAIL", "fail")
        logging.info("Result: %s" % res_str)
        if "report" in cmd_res and cmd_res["report"] != "":
            logging.info("Result data:")
            for line in cmd_res["report"].splitlines():
                logging.info(4*" " + line)
        if "msg" in cmd_res and cmd_res["msg"] != "":
            logging.info("Status message from slave: \"%s\"" % cmd_res["msg"])

        return cmd_res

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
            slave_logging_dir = os.path.join(logging_root, machine_id + "/")
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
                    match = re.match("(.+)\.py$", f)
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

    def _get_alias(self, alias):
        templates = self._parser._template_proc
        return templates._find_definition(alias)

class MessageDispatcher(ConnectionHandler):
    def __init__(self, log_ctl):
        super(MessageDispatcher, self).__init__()
        self._log_ctl = log_ctl
        self._machines = dict()

    def add_slave(self, machine, connection):
        machine_id = machine.get_id()
        self._machines[machine_id] = machine
        self.add_connection(machine_id, connection)

    def send_message(self, machine_id, data):
        soc = self.get_connection(machine_id)

        if send_data(soc, data) == False:
            msg = "Connection error from slave %s" % machine_id
            raise NetTestError(msg)

    def wait_for_result(self, machine_id):
        wait = True
        while wait:
            connected_slaves = self._connections.keys()

            messages = self.check_connections()

            remaining_slaves = self._connections.keys()

            for msg in messages:
                if msg[1]["type"] == "result" and msg[0] == machine_id:
                    wait = False
                    result = msg[1]["result"]
                else:
                    self._process_message(msg)

            if connected_slaves != remaining_slaves:
                disconnected_slaves = set(connected_slaves) -\
                                      set(remaining_slaves)
                msg = "Slaves " + str(list(disconnected_slaves)) + \
                      " disconnected from the controller."
                raise NetTestError(msg)

        return result

    def _process_message(self, message):
        if message[1]["type"] == "log":
            record = message[1]["record"]
            self._log_ctl.add_client_log(message[0], record)
        elif message[1]["type"] == "result":
            msg = "Recieved result message from different slave %s" % message[0]
            logging.debug(msg)
        elif message[1]["type"] == "if_update":
            machine = self._machines[message[0]]
            machine.interface_update(message[1])
        elif message[1]["type"] == "exception":
            msg = "Slave %s: %s" % (message[0], message[1]["Exception"])
            raise CommandException(msg)
        elif message[1]["type"] == "error":
            msg = "Recieved an error message from slave %s: %s" %\
                    (message[0], message[1]["err"])
            raise CommandException(msg)
        else:
            msg = "Unknown message type: %s" % message[1]["type"]
            raise NetTestError(msg)

    def disconnect_slave(self, machine_id):
        soc = self.get_connection(machine_id)
        self.remove_connection(soc)
        del self._machines[machine_id]
