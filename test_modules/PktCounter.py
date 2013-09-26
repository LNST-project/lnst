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

def get_pkt_count(indev_name, dport, proto):
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
    pttr = (r'\s*(\d+)\s+\d+\s+%s\s+\-\-\s+%s\s+\*\s+0\.0\.0\.0\/0\s+0\.0\.0\.0\/0\s*%s'
                                        % (p_proto, p_indev_name, p_protodport))
    data_stdout = exec_cmd("iptables -L -v -x -n")[0]
    match = re.search(pttr, data_stdout)
    if not match:
        return None
    return match.groups()[0]

class PktCounter(TestGeneric):
    def run(self):
        indev_name = self.get_opt("input_netdev_name")
        dport = self.get_opt("dport")
        proto = self.get_opt("proto")
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
            if get_pkt_count(indev_name, dport, proto) == None:
                break
            exec_cmd("iptables -D INPUT%s" % params)

        exec_cmd("iptables -I INPUT%s" % params)

        self.wait_on_interrupt()

        count = get_pkt_count(indev_name, dport, proto)

        exec_cmd("iptables -D INPUT%s" % params)

        return self.set_pass(res_data={"pkt_count": count})
