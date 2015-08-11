"""
This module defines packet counter implemented by iptables

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import logging
import re
import os
from lnst.Common.TestsCommon import TestGeneric
from lnst.Common.ExecCmd import exec_cmd, ExecCmdFail
from lnst.Common.Utils import bool_it

class PktCounter(TestGeneric):
    def _iptables_exec(self, param_str):
        if self._is_ipv6:
            cmd = "ip6tables"
        else:
            cmd = "iptables"
        return exec_cmd("%s %s" % (cmd, param_str))

    def _get_pttr(self, p_proto, p_indev_name, p_protodport):
        if self._is_ipv6:
            return r'\s*(\d+)\s+\d+\s+%s\s+%s\s+\*\s+::\/0\s+::\/0\s*%s' % (p_proto, p_indev_name, p_protodport)
        else:
            return r'\s*(\d+)\s+\d+\s+%s\s+\-\-\s+%s\s+\*\s+0\.0\.0\.0\/0\s+0\.0\.0\.0\/0\s*%s' % (p_proto, p_indev_name, p_protodport)

    def _get_pkt_count(self, indev_name, dport, proto):
        if indev_name:
            p_indev_name = indev_name
        else:
            p_indev_name = "\*"
        if proto:
            p_proto = proto
            if dport:
                p_protodport = "%s dpt:%s" % (proto, dport)
            else:
                p_protodport = ""
        else:
            p_proto = "all"
            p_protodport = ""
        pttr = self._get_pttr(p_proto, p_indev_name, p_protodport)
        data_stdout = self._iptables_exec("-L -v -x -n")[0]
        match = re.search(pttr, data_stdout)
        if not match:
            return None
        return match.groups()[0]

    def run(self):
        indev_name = self.get_opt("input_netdev_name")
        dport = self.get_opt("dport")
        proto = self.get_opt("proto")
        ipv6 = self.get_opt("ipv6")
        self._is_ipv6 = False
        if ipv6 and bool_it(ipv6):
            self._is_ipv6 = True
        params = ""
        if indev_name:
            params += " -i %s" % indev_name

        if proto:
            params += " -p %s" % proto

        if dport:
            params += " --dport %s" % dport

        '''
        Remove all same already existing rules
        '''
        while True:
            if self._get_pkt_count(indev_name, dport, proto) == None:
                break
            self._iptables_exec("-D INPUT%s" % params)

        self._iptables_exec("-I INPUT%s" % params)

        self.wait_on_interrupt()

        count = self._get_pkt_count(indev_name, dport, proto)

        self._iptables_exec("-D INPUT%s" % params)

        return self.set_pass(res_data={"pkt_count": count})
