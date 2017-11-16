"""
This module contains the API for python tasks.

Copyright 2013 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import hashlib
import re
import logging
from lnst.Common.Utils import dict_to_dot, list_to_dot, deprecated
from lnst.Common.Config import lnst_config
from lnst.Controller.XmlTemplates import XmlTemplateError
from lnst.Common.Path import Path
from lnst.Controller.PerfRepoMapping import PerfRepoMapping
from lnst.Common.Utils import Noop
from lnst.Controller.Machine import UnusedInterface

try:
    from perfrepo import PerfRepoRESTAPI
    from perfrepo import PerfRepoTestExecution
    from perfrepo import PerfRepoValue
except:
    PerfRepoRESTAPI = None
    PerfRepoTestExecution = None
    PerfRepoValue = None

# The handle to be imported from each task
ctl = None

class TaskError(Exception): pass

class ControllerAPI(object):
    """ An API class representing the controller. """

    def __init__(self, ctl, hosts):
        self._ctl = ctl
        self._result = True

        self._perf_repo_api = PerfRepoAPI()

        self._hosts = {}
        for host_id, host in hosts.iteritems():
            self._hosts[host_id] = HostAPI(self, host_id, host)

    def _run_command(self, command):
        """
            An internal wrapper that allows keeping track of the
            results of the commands within the task.

            Please, don't use this.
        """
        res = self._ctl._run_command(command)
        self._result = self._result and res["passed"]
        return res

    def get_host(self, host_id):
        """
            Get an API handle for the host from the recipe spec with
            a specific id.

            :param host_id: id of the host as defined in the recipe
            :type host_id: string

            :return: The host handle.
            :rtype: HostAPI

            :raises TaskError: If there is no host with such id.
        """
        if host_id not in self._hosts:
            raise TaskError("Host '%s' not found." % host_id)

        return self._hosts[host_id]

    def get_hosts(self):
        return self._hosts

    def get_module(self, name, options={}):
        """
            Initialize a module to be run on a host.

            :param name: name of the module
            :type name: string

            :return: The module handle.
            :rtype: ModuleAPI
        """
        return ModuleAPI(name, options)

    def wait(self, seconds):
        """
            The controller will wait for a specific amount of seconds.

            :param seconds: how long
            :type seconds: float

            :return: Command result (always passes).
            :rtype: dict
        """
        cmd = {"type": "ctl_wait", "seconds": int(seconds)}
        return self._ctl._run_command(cmd)

    def get_alias(self, alias):
        """
            Get the value of user defined alias.

            :param alias: name of user defined alias
            :type alias: string

            :return: value of a user defined alias
            :rtype: string
        """
        try:
            return self._ctl._get_alias(alias)
        except XmlTemplateError:
            return None

    def get_aliases(self):
        """
            Get all user defined aliases.

            :return: names and values of a user defined aliases
            :rtype: dict
        """
        return self._ctl._get_aliases()

    def connect_PerfRepo(self, mapping_file, url=None, username=None, password=None, max_retries=3):
        if not self._perf_repo_api.connected():
            if url is None:
                url = lnst_config.get_option("perfrepo", "url")
            if username is None:
                username = lnst_config.get_option("perfrepo", "username")
            if password is None:
                password = lnst_config.get_option("perfrepo", "password")

            if not url:
                logging.warn("No PerfRepo URL specified in config file")
            if not username:
                logging.warn("No PerfRepo username specified in config file")
            if not password:
                logging.warn("No PerfRepo password specified in config file")
            if url and username and password:
                self._perf_repo_api.connect(url, username, password, max_retries)

            root = Path(None, self._ctl._recipe_path).get_root()
            path = Path(root, mapping_file)
            self._perf_repo_api.load_mapping(path)

            if not self._perf_repo_api.connected():
                if PerfRepoRESTAPI is None:
                    logging.warn("Python PerfRepo library not found.")
                logging.warn("Connection to PerfRepo incomplete, further "\
                             "PerfRepo commands will be ignored.")
        return self._perf_repo_api

    def get_configuration(self):
        machines = self._ctl._machines
        configuration = {}
        for m_id, m in machines.items():
            configuration["machine_"+m_id] = m.get_configuration()
        return configuration

    def get_mapping(self):
        match = self._ctl.get_pool_match()
        mapping = []
        for m_id, m in match["machines"].iteritems():
            machine = {}
            machine["id"] = m_id
            machine["pool_id"] = m["target"]
            machine["hostname"] = m["hostname"]
            machine["interface"] = []
            for i_id, i in m["interfaces"].iteritems():
                interface = {}
                interface["id"] = i_id
                interface["pool_id"] = i["target"]
                interface["hwaddr"] = i["hwaddr"]
                machine["interface"].append(interface)
            mapping.append(machine)
        return mapping

class HostAPI(object):
    """ An API class representing a host machine. """

    def __init__(self, ctl, host_id, host):
        self._ctl = ctl
        self._id = host_id
        self._m = host

        self._ifaces = {}
        for interface in self._m.get_interfaces():
            if isinstance(interface, UnusedInterface):
                continue
            self._ifaces[interface.get_id()] = InterfaceAPI(interface, self)

        self._bg_id_seq = 0

    def get_id(self):
        return self._m.get_id()

    def get_configuration(self):
        return self._m.get_configuration()

    def config(self, option, value, persistent=False, netns=None):
        """
            Configure an option in /sys or /proc on the host.

            :param option: A path within /sys or /proc.
            :type option: string
            :param value: Value to be set.
            :type value: string
            :param persistent: A flag.
            :type persistent: bool
            :param netns: LNST created namespace to configure.
            :type netns: string

            :return: Command result.
            :rtype: dict
        """
        cmd = {"host": str(self._id), "type": "config"}
        cmd["options"] = [{"name": option, "value": value}]
        cmd["persistent"] = persistent
        cmd["netns"] = netns

        return self._ctl._run_command(cmd)

    def run(self, what, **kwargs):
        """
            Configure an option in /sys or /proc on the host.

            :param what: What should be run on the host.
            :type what: str or ModuleAPI

            :param bg: Run in background flag.
            :type bg: bool
            :param expect: "pass" or "fail".
            :type expect: string
            :param timeout: A time limit in seconds.
            :type timeout: int
            :param tool: Run from a tool (the same as 'from' in XML).
            :type tool: string
            :param json: Process JSON output into dictionary.
            :type json: bool

            :return: A handle for process.
            :rtype: ProcessAPI
        """
        cmd = {"host": str(self._id)}
        bg_id = None
        cmd["netns"] = None

        for arg, argval in kwargs.iteritems():
            if arg == "bg" and argval == True:
                self._bg_id_seq += 1
                cmd["bg_id"] = bg_id = self._bg_id_seq
            elif arg == "bg" and argval == False:
                continue
            elif arg == "expect":
                if str(argval) not in ["pass", "fail"]:
                    msg = "Unrecognised value of the expect attribute (%s)." \
                          % argval
                    raise TaskError(msg)

                cmd["expect"] = argval == "pass"
            elif arg == "fail_expected":
                cmd["expect"] = not argval
            elif arg == "timeout":
                try:
                    cmd["timeout"] = int(argval)
                except ValueError:
                    msg = "Timeout must be integer, not '%s'." % argval
                    raise TaskError(msg)
            elif arg == "tool":
                if type(what) == str:
                    cmd["from"] = str(argval)
                else:
                    msg = "Argument 'tool' not valid when running modules."
                    raise TaskError(msg)
            elif arg == "desc":
                cmd["desc"] = argval
            elif arg == "netns":
                cmd["netns"] = argval
            elif arg == "save_output":
                pass # now ignored as output is saved always
            elif arg == "json":
                cmd["json"] = argval
            else:
                msg = "Argument '%s' not recognised by the run() method." % arg
                raise TaskError(msg)

        if type(what) == ModuleAPI:
            cmd["type"] = "test"
            cmd["module"] = what._name
            cmd["options"] = what._opts
        elif type(what) == str:
            cmd["type"] = "exec"
            cmd["command"] = str(what)
        else:
            raise TaskError("Unable to run '%s'." % str(what))

        cmd_res = self._ctl._run_command(cmd)
        return ProcessAPI(self._ctl, self._id, cmd_res, bg_id, cmd["netns"])

    def get_interfaces(self):
        return self._ifaces

    def get_interface(self, if_id):
        return self._ifaces[if_id]

    def get_device(self, name):
        dev = self._m.dev_db_get_name(name)
        if dev:
            return DeviceAPI(dev, self)
        else:
            raise TaskError("No device with name '%s' found." % str(name))

    def get_routes(self, routes_filter = "", netns = None):
        return self._m.get_routes(routes_filter, netns)

    def mroute_init(self, table_id=None):
        return self._m.mroute_init(table_id)

    def mroute_finish(self, table_id=None):
        return self._m.mroute_finish(table_id)

    def mroute_pim_init(self, table_id=None):
        return self._m.mroute_pim_init(table_id)

    def mroute_pim_finish(self, table_id=None):
        return self._m.mroute_pim_finish(table_id)

    def mroute_table(self, index):
        return self._m.mroute_table(index)

    def mroute_add_vif_reg(self, vif_id, table_id=None):
        return self._m.mroute_add_vif_reg(vif_id, table_id)

    def mroute_del_vif_reg(self, vif_id, table_id=None):
        return self._m.mroute_del_vif_reg(vif_id, table_id)

    def mroute_add_mfc(self, group, source, source_vif, out_vifs,
                       table_id=None):
        return self._m.mroute_add_mfc(group, source, source_vif, out_vifs,
                                      table_id)

    def mroute_add_mfc_proxi(self, group, source, source_vif, out_vifs,
                             table_id=None):
        return self._m.mroute_add_mfc_proxi(group, source, source_vif,
                                            out_vifs, table_id, True)

    def mroute_del_mfc(self, group, source, source_vif, table_id=None):
        return self._m.mroute_del_mfc(group, source, source_vif, table_id)

    def mroute_del_mfc_proxi(self, group, source, source_vif, table_id=None):
        return self._m.mroute_del_mfc_proxi(group, source, source_vif,
                                            table_id, True)

    def mroute_get_notif(self, table_id=None):
        return self._m.mroute_get_notif(table_id)

    @deprecated
    def get_devname(self, if_id):
        """
            Returns devname of the interface.

            :param if_id: which interface
            :type if_id: string

            :return: Device name (e.g., eth0).
            :rtype: str
        """
        iface = self._ifaces[if_id]
        return iface.get_devname()

    @deprecated
    def get_hwaddr(self, if_id):
        """
            Returns hwaddr of the interface.

            :param if_id: which interface
            :type if_id: string

            :return: HW address (e.g., 00:11:22:33:44:55:FF).
            :rtype: str
        """
        iface = self._ifaces[if_id]
        return iface.get_hwaddr()

    @deprecated
    def get_ip(self, if_id, addr_number=0):
        """
            Returns an IP address of the interface.

            :param if_id: which interface
            :type if_id: string

            :param addr_number: which address
            :type addr_number: int

            :return: IP address (e.g., 192.168.1.10).
            :rtype: str
        """
        iface = self._ifaces[if_id]
        return iface.get_ip_addr(addr_number)

    @deprecated
    def get_prefix(self, if_id, addr_number=0):
        """
            Returns an IP address prefix (netmask)
            of the interface.

            :param if_id: which interface
            :type if_id: string

            :param addr_number: which address
            :type addr_number: int

            :return: netmask (e.g., 24).
            :rtype: str
        """
        iface = self._ifaces[if_id]
        return iface.get_ip_prefix(addr_number)

    def sync_resources(self, modules=[], tools=[]):
        res_table = self._ctl._ctl._resource_table
        sync_table = {'module': {}, 'tools': {}}
        for mod in modules:
            if mod in res_table['module']:
                sync_table['module'][mod] = res_table['module'][mod]
            else:
                msg = "Module '%s' not found on the controller"\
                        % mod
                raise TaskError(msg)

        for tool in tools:
            if tool in res_table['tools']:
                sync_table['tools'][tool] = res_table['tools'][tool]
            else:
                msg = "Tool '%s' not found on the controller"\
                        % tool
                raise TaskError(msg)

        self._m.sync_resources(sync_table)

    def _add_iface(self, if_type, if_id, netns, ip, options, slaves):
        interface = self._m.new_soft_interface(if_id, if_type)
        if_id = interface.get_id()
        iface = InterfaceAPI(interface, self)
        self._ifaces[if_id] = iface

        if slaves:
            for slave in slaves:
                if type(slave) == type(()):
                    slave_iface = slave[0]
                    slave_options = slave[1]
                    for key in slave_options:
                        interface.set_slave_option(slave_iface.get_id(),
                                                   key, slave_options[key])
                else:
                    slave_iface = slave
                interface.add_slave(slave_iface._if)

        if ip:
            interface.add_address(ip)

        if options:
            for key in options:
                interface.set_option(key, options[key])

        if netns:
            interface.set_netns(netns)

        interface.configure()
        interface.up()
        interface.address_setup()

        self._m.wait_interface_init()

        return iface

    def _remove_iface(self, iface):
        interface = iface._if
        interface.address_cleanup()
        interface.deconfigure()
        interface.cleanup()
        if_id = interface.get_id()
        self._m.remove_interface(if_id)
        self._ifaces.pop(if_id)

    def create_bond(self, if_id=None, netns=None, ip=None,
                    options=None, slaves=None):
        return self._add_iface("bond", if_id, netns, ip, options, slaves)

    def create_bridge(self, if_id=None, netns=None, ip=None,
                      options=None, slaves=None):
        return self._add_iface("bridge", if_id, netns, ip, options, slaves)

    def create_team(self, config=None, if_id=None, netns=None, ip=None,
                    slaves=None):
        out_slaves = []
        for slave in slaves:
            if type(slave) == type(()):
                slave_iface = slave[0]
                slave_config = slave[1]
                out_slaves.append((slave_iface,
                                   {"teamd_port_config": slave_config}))
            else:
                out_slaves.append(slave)

        options = {}
        if config:
            options["teamd_config"] = config

        return self._add_iface("team", if_id, netns, ip, options, out_slaves)

    def create_vlan(self, realdev_iface, vlan_tci, if_id=None, netns=None, ip=None):
        return self._add_iface("vlan", if_id, netns, ip, {"vlan_tci": vlan_tci},
                               [realdev_iface])

    def create_vxlan(self, vxlan_id, realdev_iface=None, group_ip=None,
                     remote_ip=None, if_id=None, netns=None, ip=None, options={}):
        if group_ip is None and remote_ip is None:
            raise TaskError("Either group_ip or remote_ip must be specified.")

        options.update({"id": vxlan_id,
                        "group_ip": group_ip,
                        "remote_ip": remote_ip})
        if realdev_iface is not None:
            slaves = [realdev_iface]
        else:
            slaves = []

        return self._add_iface("vxlan", if_id, netns, ip, options, slaves)

    def create_gre(self, ttl=None, tos=None,
                   key=None, ikey=None, okey=None,
                   seq=None, iseq=None, oseq=None,
                   csum=None, icsum=None, ocsum=None,
                   ul_iface=None,
                   local_ip=None, remote_ip=None,
                   if_id=None, netns=None, ip=None, options={}):

        for v, itag, iv, otag, ov in [(key, "ikey", ikey, "okey", okey),
                                      (seq, "iseq", iseq, "oseq", oseq),
                                      (csum, "icsum", icsum, "ocsum", ocsum)]:
            if v is not None:
                if iv is not None and iv != v:
                    raise TaskError("%s is overspecified" % itag)
                if ov is not None and ov != v:
                    raise TaskError("%s is overspecified" % otag)

        options.update({"ttl": ttl, "tos": tos,
                        "key": key, "ikey": ikey, "okey": okey,
                        "seq": seq, "iseq": iseq, "oseq": oseq,
                        "csum": csum, "icsum": icsum, "ocsum": ocsum,
                        "local_ip": local_ip, "remote_ip": remote_ip})

        if ul_iface is not None:
            slaves = [ul_iface]
        else:
            slaves = []

        return self._add_iface("gre", if_id, netns, ip, options, slaves)

    def create_ipip(self, ttl=None, tos=None, ul_iface=None,
                    local_ip=None, remote_ip=None,
                    if_id=None, netns=None, ip=None, options={}):

        options.update({"ttl": ttl, "tos": tos,
                        "local_ip": local_ip, "remote_ip": remote_ip})

        if ul_iface is not None:
            slaves = [ul_iface]
        else:
            slaves = []

        return self._add_iface("ipip", if_id, netns, ip, options, slaves)

    def create_dummy(self, if_id=None, netns=None, ip=None):
        return self._add_iface("dummy", if_id, netns, ip, {}, [])

    def enable_service(self, service):
        return self._m.enable_service(service)

    def disable_service(self, service):
        return self._m.disable_service(service)

    def restart_service(self, service):
        return self._m.restart_service(service)

    def copy_file_to_machine(self, local_path, remote_path=None, netns=None):
        return self._m.copy_file_to_machine(local_path, remote_path, netns)

    def get_num_cpus(self):
        return self._m.get_num_cpus()

class DeviceAPI(object):
    def __init__(self, net_device, host):
        self._dev = net_device
        self._host = host

    def get_if_index(self):
        return self._dev.get_if_index()

    def get_hwaddr(self):
        return self._dev.get_hwaddr()

    def get_devname(self):
        return self._dev.get_name()

    def get_ips(self, selector={}):
        return self._dev.get_ip_addrs(selector)

    def get_ip(self, num, selector={}):
        return self._dev.get_ip_addr(num, selector)

    def get_ifi_type(self):
        return self._dev.get_ifi_type()

    def get_state(self):
        return self._dev.get_state()

    # def get_master(self):
        # return self._dev.get_master()

    def get_slaves(self):
        return self._dev.get_slaves()

    def get_netns(self):
        return self._dev.get_netns()

    # def get_peer(self):
        # return self._dev.get_peer()

    def get_mtu(self):
        return self._dev.get_mtu()

    def set_mtu(self, mtu):
        return self._dev.set_mtu(mtu)

    def get_driver(self):
        return self._dev.get_driver()

    def get_devlink_name(self):
        return self._dev.get_devlink_name()

    def get_devlink_port_name(self):
        return self._dev.get_devlink_port_name()

class InterfaceAPI(object):
    def __init__(self, interface, host):
        self._if = interface
        self._host = host

    def get_id(self):
        return self._if.get_id()

    def get_type(self):
        return self._if.get_type()

    def get_network(self):
        return self._if.get_network()

    def get_driver(self):
        return VolatileValue(self._if.get_driver)

    def get_devname(self):
        return VolatileValue(self._if.get_devname)

    def get_hwaddr(self):
        return VolatileValue(self._if.get_hwaddr)

    def get_ip(self, ip_index=0, selector={}):
        return VolatileValue(self._if.get_address, ip_index)

    def get_ips(self, selector={}):
        return VolatileValue(self._if.get_addresses)

    @deprecated
    def get_ip_addr(self, ip_index=0):
        return self.get_ip(ip_index)

    @deprecated
    def get_ip_addrs(self):
        return self.get_ips()

    def get_prefix(self, ip_index=0):
        return VolatileValue(self._if.get_prefix, ip_index)

    @deprecated
    def get_ip_prefix(self, ip_index=0):
        return self.get_prefix(ip_index)

    def get_mtu(self):
        return VolatileValue(self._if.get_mtu)

    def set_mtu(self, mtu):
        return self._if.set_mtu(mtu)

    def link_stats(self):
        return self._if.link_stats()

    def link_cpu_ifstat(self):
        return self._if.link_cpu_ifstat()

    def set_link_up(self):
        return self._if.set_link_up()

    def set_link_down(self):
        return self._if.set_link_down()

    def get_host(self):
        return self._host

    def get_netns(self):
        return self._if.get_netns()

    def reset(self, ip=None, netns=None):
        self._if.address_cleanup()
        self._if.down()
        self._if.deconfigure()

        if ip:
            self._if.add_address(ip)

        if netns:
            self._if.set_netns(netns)

        self._if.configure()
        self._if.up()
        self._if.address_setup()

    def set_addresses(self, ips):
        self._if.set_addresses(ips)

    def add_route(self, dest, ipv6 = False):
        self._if.add_route(dest, ipv6)

    def add_nhs_route(self, dest, nhs, ipv6 = False):
        self._if.add_nhs_route(dest, nhs, ipv6)

    def del_route(self, dest, ipv6 = False):
        self._if.del_route(dest, ipv6)

    def del_nhs_route(self, dest, nhs, ipv6 = False):
        self._if.del_nhs_route(dest, nhs, ipv6)

    def enable_multicast(self):
        self._if.add_route("224.0.0.0/4", False)

    def disable_multicast(self):
        self._if.del_route("224.0.0.0/4", False)

    def destroy(self):
        self._host._remove_iface(self)

    def add_br_vlan(_self, vlan_tci, pvid=False, untagged=False,
                    self=False, master=False):
        _self._if.add_br_vlan({"vlan_id": vlan_tci, "pvid": pvid,
                               "untagged": untagged,
                               "self": self, "master": master})

    def del_br_vlan(_self, vlan_tci, pvid=False, untagged=False,
                    self=False, master=False):
        _self._if.del_br_vlan({"vlan_id": vlan_tci, "pvid": pvid,
                               "untagged": untagged,
                               "self": self, "master": master})

    def get_br_vlans(self):
        return self._if.get_br_vlans()

    def add_br_fdb(_self, hwaddr, self=False, master=False, vlan_tci=None):
        _self._if.add_br_fdb({"hwaddr": hwaddr, "self": self, "master": master,
                              "vlan_id": vlan_tci})

    def del_br_fdb(_self, hwaddr, self=False, master=False, vlan_tci=None):
        _self._if.del_br_fdb({"hwaddr": hwaddr, "self": self, "master": master,
                              "vlan_id": vlan_tci})

    def get_br_fdbs(self):
        return self._if.get_br_fdbs()

    def set_br_learning(_self, on=True, self=False, master=False):
        _self._if.set_br_learning({"on": on, "self": self, "master": master})

    def set_br_learning_sync(_self, on=True, self=False, master=False):
        _self._if.set_br_learning_sync({"on": on, "self": self,
                                        "master": master})

    def set_br_flooding(_self, on=True, self=False, master=False):
        _self._if.set_br_flooding({"on": on, "self": self, "master": master})

    def set_br_state(_self, state, self=False, master=False):
        _self._if.set_br_state({"state": state, "self": self, "master": master})

    def set_br_mcast_snooping(_self, set_on = True):
        _self._if.set_br_mcast_snooping(set_on)

    def set_br_mcast_querier(_self, set_on = True):
        _self._if.set_br_mcast_querier(set_on)

    def set_mcast_flood(self, on):
        return self._if.set_mcast_flood(on)

    def set_mcast_router(self, state):
        return self._if.set_mcast_router(state)

    def set_speed(self, speed):
        return self._if.set_speed(speed)

    def set_autoneg(self):
        return self._if.set_autoneg()

    def slave_add(self, slave_id):
        return self._if.slave_add(slave_id)

    def slave_del(self, slave_id):
        return self._if.slave_del(slave_id)

    def get_devlink_name(self):
        return self._if.get_devlink_name()

    def get_devlink_port_name(self):
        return self._if.get_devlink_port_name()

    def get_ethtool_stats(self):
        return self._if.get_ethtool_stats()

    def enable_lldp(self):
        return self._if.enable_lldp()

    def set_pause_on(self):
        return self._if.set_pause_on()

    def set_pause_off(self):
        return self._if.set_pause_off()

    def mroute_add_vif(self, vif_index, table_id=None):
        return self._if.mroute_add_vif(vif_index, table_id)

    def mroute_del_vif(self, vif_index, table_id=None):
        return self._if.mroute_del_vif(vif_index, table_id)

    def get_coalesce(self):
        return self._if.get_coalesce()

    def set_coalesce(self, cdata):
        return self._if.set_coalesce(cdata)

    def save_coalesce(self):
        return self._if.save_coalesce()

    def restore_coalesce(self):
        return self._if.restore_coalesce()

class ModuleAPI(object):
    """ An API class representing a module. """

    def __init__(self, module_name, options={}):
        self._name = module_name

        self._opts = {}
        for opt, val in options.iteritems():
            self._opts[opt] = []
            if type(val) == list:
                for v in val:
                    self._opts[opt].append({"value": str(v)})
            else:
                self._opts[opt].append({"value": str(val)})

    def get_options(self):
        return self._opts

    def set_options(self, options):
        self._opts = {}
        for opt, val in options.iteritems():
            self._opts[opt] = []
            if type(val) == list:
                for v in val:
                    self._opts[opt].append({"value": str(v)})
            else:
                self._opts[opt].append({"value": str(val)})

    def update_options(self, options):
        for opt, val in options.iteritems():
            self._opts[opt] = []
            if type(val) == list:
                for v in val:
                    self._opts[opt].append({"value": str(v)})
            else:
                self._opts[opt].append({"value": str(val)})

    def unset_option(self, option_name):
        if option_name in self._opts:
            del self._opts[option_name]

class ProcessAPI(object):
    """ An API class representing either a running or finished process. """

    def __init__(self, ctl, h_id, cmd_res, bg_id, netns):
        self._ctl = ctl
        self._host = h_id
        self._cmd_res = cmd_res
        self._bg_id = bg_id
        self._netns = netns

    def passed(self):
        """
            Returns a boolean result of the process.

            :return: True if the command passed.
            :rtype: bool
        """
        return self._cmd_res["passed"]

    def get_result(self):
        """
            Returns the whole comand result.

            :return: Command result data.
            :rtype: dict
        """
        return self._cmd_res

    def out(self):
        """
            Returns the whole command result stdout.

            :return: Command result stdout.
            :rtype: str
        """
        return self.get_result()["res_data"]["stdout"]

    def wait(self):
        """ Blocking wait until the command returns. """
        if self._bg_id:
            cmd = {"host": self._host,
                   "type": "wait",
                   "proc_id": self._bg_id,
                   "netns": self._netns}
            self._cmd_res = self._ctl._run_command(cmd)

    def intr(self):
        """ Interrupt the command. """
        if self._bg_id:
            cmd = {"host": self._host,
                   "type": "intr",
                   "proc_id": self._bg_id,
                   "netns": self._netns}
            self._cmd_res = self._ctl._run_command(cmd)

    def kill(self):
        """
            Kill the command.

            In this case, the command results are disposed. A killed
            command will always be shown as passed. If you would like
            to keep the results, use 'intr' instead.
        """
        if self._bg_id:
            cmd = {"host": self._host,
                   "type": "kill",
                   "proc_id": self._bg_id,
                   "netns": self._netns}
            self._cmd_res = self._ctl._run_command(cmd)

class VolatileValue(object):
    def __init__(self, func, *args, **kwargs):
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def get_val(self):
        return self._func(*self._args, **self._kwargs)

    def __str__(self):
        return str(self.get_val())

class PerfRepoAPI(object):
    def __init__(self):
        self._rest_api = None
        self._mapping = None

    def load_mapping(self, file_path):
        try:
            self._mapping = PerfRepoMapping(file_path.resolve())
        except:
            logging.error("Failed to load PerfRepo mapping file '%s'" %\
                          file_path.abs_path())
            self._mapping = None

    def get_mapping(self):
        return self._mapping

    def connected(self):
        if self._rest_api is not None and self._rest_api.connected() and\
                self._mapping is not None:
            return True
        else:
            return False

    def connect(self, url, username, password, max_retries=0):
        if PerfRepoRESTAPI is not None:
            self._rest_api = PerfRepoRESTAPI(url, username, password)
            self._rest_api.set_retries(max_retries)
            if not self._rest_api.connected():
                self._rest_api = None
        else:
            self._rest_api = None

    def new_result(self, mapping_key, name, hash_ignore=[]):
        if not self.connected():
            return Noop()

        mapping_id = self._mapping.get_id(mapping_key)
        if mapping_id is None:
            logging.debug("Test key '%s' has no mapping defined!" % mapping_key)
            return Noop()

        logging.debug("Test key '%s' mapped to id '%s'" % (mapping_key,
                                                           mapping_id))

        try:
            test = self._rest_api.test_get_by_id(mapping_id, log=False)
        except Exception as e:
            test = None
            logging.error(str(e))
        if test is None:
            try:
                test = self._rest_api.test_get_by_uid(mapping_id, log=False)
            except Exception as e:
                test = None
                logging.error(str(e))

        if test is not None:
            test_url = self._rest_api.get_obj_url(test)
            logging.debug("Found Test with id='%s' and uid='%s'! %s" % \
                            (test.get_id(), test.get_uid(), test_url))
        else:
            logging.debug("No Test with id or uid '%s' found!" % mapping_id)
            return Noop()

        logging.info("Creating a new result object for PerfRepo")
        result = PerfRepoResult(test, name, hash_ignore)
        return result

    def save_result(self, result, official_result=False):
        if isinstance(result, Noop):
            return
        elif not self.connected():
            raise TaskError("Not connected to PerfRepo.")
        elif isinstance(result, PerfRepoResult):
            if len(result.get_testExecution().get_values()) < 1:
                logging.debug("PerfRepoResult with no result data, skipping "\
                              "send to PerfRepo.")
                return

            h = result.generate_hash()
            if official_result:
                logging.debug("Adding hash '%s' as tag to result." % h)
                result.add_tag(h)
            else:
                logging.debug("Unofficial results - skipping hash tag.")
            logging.info("Sending TestExecution to PerfRepo.")
            try:
                self._rest_api.testExecution_create(result.get_testExecution())
            except Exception as e:
                logging.error(str(e))
                return

            report_id = self._mapping.get_id(h)
            if not report_id and result.get_testExecution().get_id() != None:
                logging.debug("No mapping defined for hash '%s'" % h)
                logging.debug("If you want to create a new report and set "\
                              "this result as the baseline run this command:")
                cmd = "perfrepo-cli report create"
                cmd += " name REPORTNAME"

                test = result.get_test()
                cmd += " chart CHARTNAME"
                cmd += " testid %s" % test.get_id()
                series_num = 0
                for m in test.get_metrics():
                    cmd += " series NAME%d" % series_num
                    cmd += " metric %s" % m.get_id()
                    cmd += " tags %s" % h
                    series_num += 1
                cmd += " baseline BASELINENAME"
                cmd += " execid %s" % result.get_testExecution().get_id()
                cmd += " metric %s" % test.get_metrics()[0].get_id()
                logging.debug(cmd)
        else:
            raise TaskError("Parameter result must be an instance "\
                            "of PerfRepoResult")

    def get_baseline(self, report_id):
        if report_id is None or not self.connected():
            return Noop()

        try:
            report = self._rest_api.report_get_by_id(report_id, log=False)
        except Exception as e:
            report = None
            logging.error(str(e))
        if report is None:
            logging.debug("No report with id %s found!" % report_id)
            return Noop()
        logging.debug("Report found: %s" %\
                        self._rest_api.get_obj_url(report))

        baseline = report.get_baseline()

        if baseline is None:
            logging.debug("No baseline set for report %s" %\
                            self._rest_api.get_obj_url(report))
            return Noop()

        baseline_exec_id = baseline["execId"]
        try:
            baseline_testExec = self._rest_api.testExecution_get(baseline_exec_id,
                                                                 log=False)
        except Exception as e:
            baseline_testExec = None
            logging.error(str(e))

        if baseline_testExec is not None:
            logging.debug("TestExecution of baseline: %s" %\
                            self._rest_api.get_obj_url(baseline_testExec))
        else:
            logging.debug("Couldn't get TestExecution of baseline.")
            return Noop()
        return PerfRepoBaseline(baseline_testExec)

    def get_baseline_of_result(self, result):
        if not isinstance(result, PerfRepoResult) or not self.connected():
            return Noop()

        res_hash = result.generate_hash()
        logging.debug("Result hash is: '%s'" % res_hash)

        report_id = self._mapping.get_id(res_hash)
        if report_id is not None:
            logging.debug("Hash '%s' maps to report id '%s'" % (res_hash,
                                                               report_id))
        else:
            logging.debug("Hash '%s' has no mapping defined!" % res_hash)
            return Noop()

        baseline = self.get_baseline(report_id)

        if baseline.get_texec() is None:
            logging.debug("No baseline set for results with hash %s" % res_hash)
        return baseline

    def compare_to_baseline(self, result, report_id, metric_name):
        if not self.connected():
            return False
        baseline_testExec = self.get_baseline(report_id)
        result_testExec = result.get_testExecution()

        return self.compare_testExecutions(result_testExec,
                                           baseline_testExec,
                                           metric_name)

    def compare_testExecutions(self, first, second, metric_name):
        first_value = first.get_value(metric_name)
        first_min = first.get_value(metric_name + "_min")
        first_max = first.get_value(metric_name + "_max")

        second_value = second.get_value(metric_name)
        second_min = second.get_value(metric_name + "_min")
        second_max = second.get_value(metric_name + "_max")

        comp = second_value.get_comparator()
        if comp == "HB":
            if second_min.get_result() > first_max.get_result():
                return False
            return True
        elif comp == "LB":
            if first_min.get_result() > second_max.get_result():
                return False
            return True
        else:
            return False
        return False

class PerfRepoResult(object):
    def __init__(self, test, name, hash_ignore=[]):
        self._test = test
        self._testExecution = PerfRepoTestExecution()
        self._testExecution.set_testId(test.get_id())
        self._testExecution.set_testUid(test.get_uid())
        self._testExecution.set_name(name)
        self.set_configuration(ctl.get_configuration())
        self._hash_ignore = hash_ignore

    def add_value(self, val_name, value):
        perf_value = PerfRepoValue()
        perf_value.set_metricName(val_name)
        perf_value.set_result(value)

        self._testExecution.add_value(perf_value)

    def set_configuration(self, configuration=None):
        if configuration is None:
            configuration = ctl.get_configuration()
        for pair in dict_to_dot(configuration, "configuration."):
            self._testExecution.add_parameter(pair[0], pair[1])

    def set_mapping(self, mapping=None):
        if mapping is None:
            mapping = ctl.get_mapping()
        for pair in list_to_dot(mapping, "mapping.", "machine"):
            self._testExecution.add_parameter(pair[0], pair[1])

    def set_tag(self, tag):
        self._testExecution.add_tag(tag)

    def add_tag(self, tag):
        self.set_tag(tag)

    def set_tags(self, tags):
        for tag in tags:
            self.set_tag(tag)

    def add_tags(self, tags):
        self.set_tags(tags)

    def set_parameter(self, name, value):
        self._testExecution.add_parameter(name, value)

    def set_parameters(self, params):
        for name, value in params:
            self.set_parameter(name, value)

    def set_hash_ignore(self, hash_ignore):
        self._hash_ignore = hash_ignore

    def set_comment(self, comment):
        if comment:
            self._testExecution.set_comment(comment)

    def get_hash_ignore(self):
        return self._hash_ignore

    def get_testExecution(self):
        return self._testExecution

    def get_test(self):
        return self._test

    def generate_hash(self, ignore=[]):
        ignore.extend(self._hash_ignore)
        tags = self._testExecution.get_tags()
        params = self._testExecution.get_parameters()

        sha1 = hashlib.sha1()
        sha1.update(self._testExecution.get_testUid())
        for i in sorted(tags):
            sha1.update(i)
        for i in sorted(params, key=lambda x: x[0]):
            skip = False
            for j in ignore:
                if re.search(j, i[0]):
                    skip = True
                    break
            if skip:
                continue
            sha1.update(i[0])
            sha1.update(str(i[1]))
        return sha1.hexdigest()

class PerfRepoBaseline(object):
    def __init__(self, texec):
        self._texec = texec

    def get_value(self, name):
        if self._texec is None:
            return None
        perfrepovalue = self._texec.get_value(name)
        return perfrepovalue.get_result()

    def get_texec(self):
        return self._texec
