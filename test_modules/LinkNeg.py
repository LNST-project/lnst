"""
This module defines the link negotiation test
"""

__author__ = """
idosch@mellanox.com (Ido Schimmel)
"""

import logging
import re
from lnst.Common.TestsCommon import TestGeneric
from lnst.Common.Utils import bool_it
from lnst.Common.ExecCmd import exec_cmd
from pyroute2 import IPDB


class LinkNeg(TestGeneric):
    def get_speed(self, iface):
        data_stdout = exec_cmd("ethtool %s" % iface)[0]
        match = re.search('Speed: ([0-9]*)', data_stdout)
        return 0 if match is None else int(match.group(1))

    def _cb(self, ipdb, msg, action):
        if action == 'RTM_NEWLINK':
            self.oper_state = msg.get_attr('IFLA_OPERSTATE', '')

    def run(self):
        logging.info('Started LinkNeg...')
        iface = self.get_mopt('iface')
        state = bool_it(self.get_mopt('state'))
        admin_speed = self.get_opt('speed', default=0)
        timeout = self.get_opt('timeout', default=10)

        ip = IPDB()
        self.oper_state = ip.interfaces[iface]['operstate']
        wd = ip.watchdog(ifname=iface)
        cuid = ip.register_callback(self._cb)

        wd.wait(timeout=timeout)
        ip.unregister_callback(cuid)
        ip.release()

        admin_state = 'UP' if state else 'DOWN'
        oper_state = self.oper_state

        if admin_state == oper_state and admin_speed:
            oper_speed = self.get_speed(iface)
        else:
            oper_speed = 0

        res_data = {'admin_state': admin_state, 'oper_state': oper_state}
        if admin_speed:
            res_data['admin_speed'] = "%s Mb/s" % admin_speed
            res_data['oper_speed'] = "%s Mb/s" % oper_speed

        if admin_state == oper_state and admin_speed == oper_speed:
            self.set_pass(res_data)
        else:
            self.set_fail(res_data)
