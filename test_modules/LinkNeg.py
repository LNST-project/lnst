"""
This module defines the link negotiation test
"""

__author__ = """
idosch@mellanox.com (Ido Schimmel)
"""

import logging
from lnst.Common.TestsCommon import TestGeneric
from lnst.Common.Utils import bool_it
from pyroute2 import IPDB


class LinkNeg(TestGeneric):
    def _cb(self, ipdb, msg, action):
        if action == 'RTM_NEWLINK':
            self.oper_state = msg.get_attr('IFLA_OPERSTATE', '')

    def run(self):
        logging.info('Started LinkNeg...')
        iface = self.get_mopt('iface')
        state = bool_it(self.get_mopt('state'))
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
        res_data = {'admin_state': admin_state, 'oper_state': oper_state}

        if admin_state == oper_state:
            self.set_pass(res_data)
        else:
            self.set_fail(res_data)
