"""
Defines the MachineMapper class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import logging
from lnst.Controller.Common import ControllerError

class MapperError(ControllerError):
    pass

def format_match_description(match):
    output = []
    output.append("Pool match description:")
    if match["virtual"]:
        output.append("  Setup is using virtual machines.")
    for m_id, m in sorted(match["machines"].items()):
        output.append("  host \"{}\" uses \"{}\"".format(m_id, m["target"]))
        for if_id, match in sorted(m["interfaces"].items()):
            pool_id = match["target"]
            output.append("    interface \"{}\" matched to \"{}\"".
                          format(if_id, pool_id))
    return "\n".join(output)

class MachineMapper(object):
    """Implements a matching algorithm that maps requirements to available hosts

    In this specific class this is implemented with backtracking, however
    testers are free to implement their own algorithm as long as they respect
    the API of this class as it needs to integrate with the rest of LNST.

    Since the API is not fully defined yet and depends on the interaction with
    the AgentPoolManager (also needs a fully defined API), implementing your
    own MachineMapper class is not recommended yet. However since, the
    Controller class accepts the 'mapper' parameter it is possible if done
    properly.

    TODO The Interface will be separated into an abstract class to clearly
    define the required API. ABC?
    """
    def __init__(self):
        self._pools = {}
        self._pool_stack = []
        self._pool = {}
        self._pool_name = None
        self._mreqs = {}
        self._unmatched_req_machines = []
        self._matched_pool_machines = []
        self._machine_stack = []
        self._net_label_mapping = {}
        self._virtual_matching = False

    def set_requirements(self, mreqs):
        """set the requirements to be used by the matching algorithm

        This should be a specially formatted dictionary to work.
        TODO Should probably be reworked to work with something more
        flexible.
        """
        self._mreqs = mreqs

    def set_pools_manager(self, pools_manager):
        """set the pools manager to be used by the matching algorithm

        This class does not use pools manager anymore. Method just gets the pools.
        This needs to be a specially formatted dictionary returned by get_pools
        method of a AgentPoolManager class.
        """
        self._pools = pools_manager.get_pools()

    def reset_match_state(self):
        """resets the state of the backtracking algorithm"""
        self._net_label_mapping = {}
        self._machine_stack = []
        self._unmatched_req_machines = sorted(list(self._mreqs.keys()), reverse=True)

        self._pool_stack = list(self._pools.keys())
        if len(self._pool_stack) > 0:
            self._pool_name = self._pool_stack.pop()
            self._pool = self._pools[self._pool_name]

        self._unmatched_pool_machines = []
        for p_id, p_machine in sorted(list(self._pool.items()), reverse=True):
            if self._virtual_matching:
                if "libvirt_domain" in p_machine["params"]:
                    self._unmatched_pool_machines.append(p_id)
            else:
                self._unmatched_pool_machines.append(p_id)

        if len(self._pool) > 0 and len(self._mreqs) > 0:
            self._push_machine_stack()

    def matches(self, **kwargs):
        """Generator method which calls the matching algorithm

        Args:
            multimatch -- if False or not specified, will only return the first
                match. Otherwise repeated calls of this method will return
                more possible mappings until no more are possible.

        Returns:
            The matched mapping or requirements to pool Machines.
        """
        logging.info("Matching machines, without virtuals.")
        self.reset_match_state()
        matched = False

        while self._match():
            matched = True
            yield self.get_mapping()
            if "multimatch" not in kwargs or not kwargs["multimatch"]:
                return

        if "allow_virt" in kwargs and kwargs["allow_virt"]:
            logging.info("Match failed for normal machines, falling back "\
                         "to matching virtual machines.")
            self._virtual_matching = True
            self.reset_match_state()
            while self._match():
                matched = True
                yield self.get_mapping()
                if "multimatch" not in kwargs or not kwargs["multimatch"]:
                    return
        if not matched:
            msg = "This setup cannot be provisioned with the current pool."
            raise MapperError(msg)

    def _match(self):
        logging.info("Trying match with pool: %s" % self._pool_name)
        while len(self._machine_stack)>0:
            stack_top = self._machine_stack[-1]
            if self._virtual_matching and stack_top["virt_matched"]:
                if stack_top["current_match"] != None:
                    cur_match = stack_top["current_match"]
                    self._unmatched_pool_machines.append(cur_match)
                    stack_top["current_match"] = None
                stack_top["virt_matched"] = False

            if self._if_match():
                if len(self._unmatched_req_machines) > 0:
                    self._push_machine_stack()
                    continue
                else:
                    return True
            else:
                #unmap the pool machine
                if stack_top["current_match"] != None:
                    cur_match = stack_top["current_match"]
                    self._unmatched_pool_machines.append(cur_match)
                stack_top["current_match"] = None

                mreq_m_id = stack_top["m_id"]
                while len(stack_top["remaining_matches"]) > 0:
                    pool_m_id = stack_top["remaining_matches"].pop()
                    if self._check_machine_compatibility(mreq_m_id, pool_m_id):
                        #map compatible pool machine
                        stack_top["current_match"] = pool_m_id
                        stack_top["unmatched_pool_ifs"] = \
                            sorted(list(self._pool[pool_m_id]["interfaces"].keys()),
                                   reverse=True)
                        self._unmatched_pool_machines.remove(pool_m_id)
                        break

                if stack_top["current_match"] != None:
                    #clear if mapping
                    stack_top["if_stack"] = []
                    #next iteration will match the interfaces
                    if not self._virtual_matching:
                        self._push_if_stack()
                    continue
                else:
                    self._pop_machine_stack()
                    if len(self._machine_stack) == 0 and\
                       len(self._pool_stack) > 0:
                        logging.info("Match with pool %s not found." %
                                     self._pool_name)
                        self._pool_name = self._pool_stack.pop()
                        self._pool = self._pools[self._pool_name]
                        logging.info("Trying match with pool: %s" %
                                     self._pool_name)

                        self._unmatched_pool_machines = []
                        for p_id, p_machine in sorted(list(self._pool.items()), reverse=True):
                            if self._virtual_matching:
                                if "libvirt_domain" in p_machine["params"]:
                                    self._unmatched_pool_machines.append(p_id)
                            else:
                                self._unmatched_pool_machines.append(p_id)

                        if len(self._pool) > 0 and len(self._mreqs) > 0:
                            self._push_machine_stack()
                    continue
        return False

    def _if_match(self):
        m_stack_top = self._machine_stack[-1]
        if_stack = m_stack_top["if_stack"]

        if self._virtual_matching:
            if m_stack_top["current_match"] != None:
                m_stack_top["virt_matched"] = True
                return True
            else:
                return False

        while len(if_stack) > 0:
            stack_top = if_stack[-1]

            req_m = self._mreqs[m_stack_top["m_id"]]
            pool_m = self._pool[m_stack_top["current_match"]]
            req_if = req_m["interfaces"][stack_top["if_id"]]
            req_net_label = req_if["network"]

            if stack_top["current_match"] != None:
                cur_match = stack_top["current_match"]
                m_stack_top["unmatched_pool_ifs"].append(cur_match)
                pool_if = pool_m["interfaces"][cur_match]
                pool_net_label = pool_if["network"]
                net_label_mapping = self._net_label_mapping[req_net_label]
                if net_label_mapping == (pool_net_label, m_stack_top["m_id"],
                                         stack_top["if_id"]):
                    del self._net_label_mapping[req_net_label]
            stack_top["current_match"] = None

            while len(stack_top["remaining_matches"]) > 0:
                pool_if_id = stack_top["remaining_matches"].pop()
                pool_if = pool_m["interfaces"][pool_if_id]
                if self._check_interface_compatibility(req_if, pool_if):
                    #map compatible interfaces
                    stack_top["current_match"] = pool_if_id
                    if req_net_label not in self._net_label_mapping:
                        self._net_label_mapping[req_net_label] =\
                                                   (pool_if["network"],
                                                   m_stack_top["m_id"],
                                                   stack_top["if_id"])
                    m_stack_top["unmatched_pool_ifs"].remove(pool_if_id)
                    break

            if stack_top["current_match"] != None:
                if len(m_stack_top["unmatched_ifs"]) > 0:
                    self._push_if_stack()
                    continue
                else:
                    return True
            else:
                self._pop_if_stack()
                continue
        return False

    def _push_machine_stack(self):
        machine_match = {}
        machine_match["m_id"] = self._unmatched_req_machines.pop()
        machine_match["current_match"] = None
        machine_match["remaining_matches"] = list(self._unmatched_pool_machines)
        machine_match["if_stack"] = []

        machine = self._mreqs[machine_match["m_id"]]
        machine_match["unmatched_ifs"] = sorted(list(machine["interfaces"].keys()),
                                                reverse=True)
        machine_match["unmatched_pool_ifs"] = []

        if self._virtual_matching:
            machine_match["virt_matched"] = False

        self._machine_stack.append(machine_match)

    def _pop_machine_stack(self):
        stack_top = self._machine_stack.pop()
        self._unmatched_req_machines.append(stack_top["m_id"])

    def _push_if_stack(self):
        m_stack_top = self._machine_stack[-1]
        if_match = {}
        if_match["if_id"] = m_stack_top["unmatched_ifs"].pop()
        if_match["current_match"] = None
        if_match["remaining_matches"] = list(m_stack_top["unmatched_pool_ifs"])

        m_stack_top["if_stack"].append(if_match)

    def _pop_if_stack(self):
        m_stack_top = self._machine_stack[-1]
        if_stack_top = m_stack_top["if_stack"].pop()
        m_stack_top["unmatched_ifs"].append(if_stack_top["if_id"])

    def _check_machine_compatibility(self, req_id, pool_id):
        req_machine = self._mreqs[req_id]
        pool_machine = self._pool[pool_id]
        for param, value in list(req_machine["params"].items()):
            # skip empty parameters
            if len(value) == 0:
                continue
            if param not in pool_machine["params"] or\
               value != pool_machine["params"][param]:
                return False
        return True

    def _check_interface_compatibility(self, req_if, pool_if):
        label_mapping = self._net_label_mapping
        for req_label, mapping in list(label_mapping.items()):
            if req_label == req_if["network"] and\
               mapping[0] != pool_if["network"]:
                return False
            if mapping[0] == pool_if["network"] and\
               req_label != req_if["network"]:
                return False
        for param, value in list(req_if["params"].items()):
            # skip empty parameters
            if len(value) == 0:
                continue
            if param not in pool_if["params"] or\
               value != pool_if["params"][param]:
                return False
        return True

    def get_mapping(self):
        mapping = {"machines": {}, "networks": {}, "virtual": False,
                   "pool_name": self._pool_name}

        for req_label, label_map in list(self._net_label_mapping.items()):
            mapping["networks"][req_label] = label_map[0]

        for machine in self._machine_stack:
            m_map = mapping["machines"][machine["m_id"]] = {}

            m_map["target"] = machine["current_match"]

            hostname = self._pool[m_map["target"]]["params"]["hostname"]
            m_map["hostname"] = hostname

            interfaces = m_map["interfaces"] = {}
            if_stack = machine["if_stack"]
            for interface in if_stack:
                i = interfaces[interface["if_id"]] = {}
                i["target"] = interface["current_match"]
                pool_if = self._pool[m_map["target"]]["interfaces"][i["target"]]
                i["hwaddr"] = pool_if["params"]["hwaddr"]


        if self._virtual_matching:
            mapping["virtual"] = True
        return mapping


class ContainerMapper(object):
    """Implements simple matching algorithm that maps containers to requirements.
    Containers are created in :py:class:`lnst.Controller.ContainerPoolManager.ContainerPoolManager` using requirements.

    """

    def __init__(self):
        self._pool_manager = None
        self._mreqs = {}

    def set_requirements(self, mreqs: dict):
        self._mreqs = mreqs

    def set_pools_manager(self, pool_manager):
        """:py:class:`lnst.Controller.MachineMapper.ContainerMapper` does not support multiple pools but it requires pool manager."""
        self._pool_manager = pool_manager

    @staticmethod
    def _map_machine_interface(network_name, interfaces: dict):
        """Mapping machine interface to network using network name inside interface dict."""
        for inf_id, interface in interfaces.items():
            if interface["network"] == network_name:
                return inf_id, interface

    def matches(self):
        """1:1 mapping of containers to requirements"""
        self._pool_manager.process_reqs(self._mreqs)

        mapping = {
            "machines": {},
            "networks": {},
            "virtual": False,
            "pool_name": "default",
        }
        pool = self._pool_manager.get_pool()

        for m_id, reqs in self._mreqs.items():
            hostname = pool[m_id]["params"]["hostname"]
            machine = mapping["machines"][m_id] = {
                "target": m_id,
                "hostname": hostname,
                "interfaces": {},
            }

            for inf_id, infs in reqs["interfaces"].items():
                network_name = self._pool_manager.get_network_name(infs["network"])

                machine_inf_id, machine_inf = self._map_machine_interface(
                    network_name, pool[m_id]["interfaces"]
                )

                machine["interfaces"][inf_id] = {
                    "target": machine_inf_id,
                    "hwaddr": machine_inf["params"]["hwaddr"],
                }

        for name, network in self._pool_manager.get_networks().items():
            mapping["networks"][name] = network.name

        yield mapping
