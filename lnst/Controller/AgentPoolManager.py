"""
This module contains implementaion of AgentPoolManager class that
takes care of loading pools and checking machine availability

Most of the AgentPoolManager class is copied over from the old AgentPool class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import logging
import os
import errno
import re
import socket
import select
from lnst.Common.NetUtils import normalize_hwaddr
from lnst.Controller.Common import ControllerError
from lnst.Controller.Machine import Machine
from lnst.Controller.AgentMachineParser import AgentMachineParser
from lnst.Common.Colours import decorate_with_preset
from lnst.Common.Utils import check_process_running

class PoolManagerError(ControllerError):
    pass

class AgentPoolManager(object):
    """
    This class is responsible for managing test machines that
    are available at the controler and can be used for testing.
    """
    def __init__(self, pools, msg_dispatcher, ctl_config, pool_checks=True):
        self._map = {}
        self._pools = {}
        self._pool = {}
        self._msg_dispatcher = msg_dispatcher
        self._ctl_config = ctl_config

        self._allow_virt = ctl_config.get_option("environment",
                                                 "allow_virtual")
        self._allow_virt &= check_process_running("libvirtd")
        self._pool_checks = pool_checks

        logging.info("Checking machine pool availability.")
        for pool_name, pool_dir in list(pools.items()):
            self._pools[pool_name] = {}
            self.add_dir(pool_name, pool_dir)
            if len(self._pools[pool_name]) == 0:
                del self._pools[pool_name]

        self._machines = {}
        for pool_name, machines in list(self._pools.items()):
            pool = self._machines[pool_name] = {}
            for m_id, m_spec in list(machines.items()):
                params = m_spec["params"]

                hostname = params["hostname"]

                if "libvirt_domain" in params:
                    libvirt_domain = params["libvirt_domain"]
                else:
                    libvirt_domain = None

                if "rpc_port" in params:
                    rpc_port = params["rpc_port"]
                else:
                    rpc_port = None

                pool[m_id] = Machine(m_id, hostname, self._msg_dispatcher,
                                     ctl_config, libvirt_domain, rpc_port,
                                     m_spec["security"], params)
                pool[m_id].init_connection()
                #TODO check if all described devices are available

        logging.info("Finished loading pools.")

    def get_pools(self):
        return self._pools

    def get_pool(self, pool_name):
        return self._pools[pool_name]

    def get_machine_pools(self):
        return self._machines

    def get_machine_pool(self, pool_name):
        return self._machines[pool_name]

    def add_dir(self, pool_name, dir_path):
        logging.info("Processing pool '%s', directory '%s'" % (pool_name,
                                                               dir_path))
        pool = self._pools[pool_name]

        try:
            dentries = os.listdir(dir_path)
        except OSError:
            logging.warn("Directory '%s' does not exist for pool '%s'" %
                                                                  (dir_path,
                                                                   pool_name))
            return

        for dirent in dentries:
            m_id, m = self.add_file(pool_name, dir_path, dirent)
            if m_id != None and m != None:
                pool[m_id] = m

        if len(pool) == 0:
            logging.warn("No machines found in pool '%s', directory '%s'" %
                                                                   (pool_name,
                                                                    dir_path))

        max_len = 0
        for m_id in list(pool.keys()):
            if len(m_id) > max_len:
                max_len = len(m_id)

        if self._pool_checks:
            check_sockets = {}
            for m_id, m in sorted(pool.items()):
                hostname = m["params"]["hostname"]
                if "rpc_port" in m["params"]:
                    port = int(m["params"]["rpc_port"])
                else:
                    port = self._ctl_config.get_option('environment', 'rpcport')

                logging.debug("Querying machine '%s': %s:%s" %\
                                                (m_id, hostname, port))

                s = socket.socket()
                s.settimeout(0)
                try:
                    s.connect((hostname, port))
                except socket.error as msg:
                    # if the error is other than EINPROGRESS, e.g. the stack
                    # could not resolve name, the machine should become unavailable
                    try:
                        en = msg.errno
                    except AttributeError:
                        en = 0

                    if en != errno.EINPROGRESS:
                        pool[m_id]["available"] = False
                        s.close()
                        logging.debug("Bypassing machine '%s' (%s)" %
                            (m_id, msg))
                        continue

                check_sockets[s] = m_id

            while len(check_sockets) > 0:
                rl, wl, el = select.select([], list(check_sockets.keys()), [])
                for s in wl:
                    err = s.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                    m_id = check_sockets[s]
                    if err == 0:
                        pool[m_id]["available"] = True
                        s.shutdown(socket.SHUT_RDWR)
                        s.close()
                        del check_sockets[s]
                    else:
                        pool[m_id]["available"] = False
                        s.close()
                        del check_sockets[s]
        else:
            for m_id in list(pool.keys()):
                pool[m_id]["available"] = True

        for m_id in sorted(list(pool.keys())):
            m = pool[m_id]
            if m["available"]:
                if 'libvirt_domain' in m['params']:
                    libvirt_msg = "   libvirt_domain: %s" %\
                                        m['params']['libvirt_domain']
                else:
                    libvirt_msg = ""
                msg = "%s%s [%s] %s" % (m_id, (max_len - len(m_id)) * " ",
                                        decorate_with_preset("UP", "pass"),
                                        libvirt_msg)
            else:
                msg = "%s%s [%s]" % (m_id, (max_len - len(m_id)) * " ",
                                     decorate_with_preset("DOWN", "fail"))
                del pool[m_id]

            logging.info(msg)

    def add_file(self, pool_name, dir_path, dirent):
        filepath = dir_path + "/" + dirent
        pool = self._pools[pool_name]
        if os.path.isfile(filepath) and re.search(r"\.xml$", filepath, re.I):
            dirname, basename = os.path.split(filepath)
            m_id = re.sub(r"\.[xX][mM][lL]$", "", basename)

            parser = AgentMachineParser(filepath, self._ctl_config)
            xml_data = parser.parse()
            machine_spec = self._process_machine_xml_data(m_id, xml_data)

            if 'libvirt_domain' in machine_spec['params'] and \
               not self._allow_virt:
                   logging.debug("libvirtd not running disabled. "\
                                 "Removing libvirt_domain from "\
                                 "machine '%s'" % m_id)
                   del machine_spec['params']['libvirt_domain']

            # Check if there isn't any machine with the same
            # hostname or libvirt_domain already in the pool
            for pm_id, m in pool.items():
                pm = m["params"]
                rm = machine_spec["params"]
                if pm["hostname"] == rm["hostname"]:
                    msg = "You have the same machine listed twice in " \
                          "your pool ('%s' and '%s')." % (m_id, pm_id)
                    raise PoolManagerError(msg)

                if "libvirt_domain" in rm and "libvirt_domain" in pm and \
                   pm["libvirt_domain"] == rm["libvirt_domain"]:
                    msg = "You have the same libvirt_domain listed twice in " \
                          "your pool ('%s' and '%s')." % (m_id, pm_id)
                    raise PoolManagerError(msg)

            return (m_id, machine_spec)
        return (None, None)

    def _process_machine_xml_data(self, m_id, machine_xml_data):
        machine_spec = {"interfaces": {}, "params":{}, "security": {}}

        # process parameters
        if "params" in machine_xml_data:
            for param in machine_xml_data["params"]:
                name = str(param["name"])
                value = str(param["value"])
                machine_spec["params"][name] = value

        mandatory_params = ["hostname"]
        for p in mandatory_params:
            if p not in machine_spec["params"]:
                msg = "Mandatory parameter '%s' missing for machine %s." \
                        % (p, m_id)
                raise PoolManagerError(msg, machine_xml_data["params"])

        # process interfaces
        if "interfaces" in machine_xml_data:
            for iface in machine_xml_data["interfaces"]:
                if_id = iface["id"]
                iface_spec = self._process_iface_xml_data(m_id, iface)

                # validity check, MAC and id must be unique
                if if_id in machine_spec["interfaces"]:
                    msg = "Duplicate interface id '%s'." % if_id
                    raise PoolManagerError(msg, iface)

                if_hwaddr = iface_spec["params"]["hwaddr"]
                hwaddr_dups = [ k for k, v in machine_spec["interfaces"].items()\
                                if v["params"]["hwaddr"] == if_hwaddr ]
                if len(hwaddr_dups) > 0:
                    msg = "Duplicate MAC address %s for interface '%s' and '%s'."\
                          % (if_hwaddr, if_id, hwaddr_dups[0])
                    raise PoolManagerError(msg, iface)

                machine_spec["interfaces"][if_id] = iface_spec

        machine_spec["security"] = machine_xml_data["security"]

        return machine_spec

    def _process_iface_xml_data(self, m_id, iface):
        if_id = iface["id"]
        iface_spec = {"params": {}}
        iface_spec["network"] = iface["network"]

        for param in iface["params"]:
            name = str(param["name"])
            value = str(param["value"])

            if name == "hwaddr":
                iface_spec["params"][name] = normalize_hwaddr(value)
            else:
                iface_spec["params"][name] = value

        mandatory_params = ["hwaddr"]
        for p in mandatory_params:
            if p not in iface_spec["params"]:
                msg = "Mandatory parameter '%s' missing for machine %s, " \
                      "interface '%s'." % (p, m_id, if_id)
                raise PoolManagerError(msg, iface["params"])

        return iface_spec
