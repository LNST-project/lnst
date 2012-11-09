"""
Wrapper for executing the multicast test tools in LNST

Copyright 2012 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import logging
import re
from lnst.Common.TestsCommon import TestGeneric
from lnst.Controller.NetTestCommand import CommandException
from lnst.Common.ExecCmd import exec_cmd

class TestMulticast(TestGeneric):
    """ Wrapper for executing the multicast test tools in LNST

    Running this test executes specified test setup from
    multicast tools and evaluates the results. The behavior
    is defined entirely by behavior of the selected setup.

    """

    _conditions = {}

    @staticmethod
    def _remove_mask(address_in_string):
        """ Remove mask suffix from the IP address """
        if address_in_string != None:
            return address_in_string.split('/')[0]
        else:
            return address_in_string

    def _compose_cmd(self):
        """ Setup a command from the recipe options """
        cmd  = ""
        opts = {}

        setup = self.get_mopt("setup")
        opts["multicast_address"] = self._remove_mask(self.get_opt("address"))
        opts["port"] = self.get_opt("port")
        opts["interface"] = self._remove_mask(self.get_opt("interface"))
        opts["duration"] = self.get_opt("duration")

        # sender-specific
        opts["loop"] = self.get_opt("loop")
        opts["ttl"] = self.get_opt("ttl")
        opts["delay"] = self.get_opt("delay")

        # receiver-specific
        opts["source_address"] = self._remove_mask(self.get_opt("source"))

        # igmp-specific
        opts["query_type"] = self.get_opt("query_type")
        opts["dest_address"] = self.get_opt("dest_address")
        opts["max_resp_time"] = self.get_opt("max_resp_time")

        cmd  = "./{0} ".format(setup)

        for optname, optval in opts.iteritems():
            if optval != None:
                cmd += "--{0} \"{1}\" ".format(optname, optval)

        return cmd

    def _evaluate_result(self, name, value):
        """ Check if the result meets required conditions """
        if name in self._conditions:
            try:
                float(value)
            except ValueError:
                value = '"' + value + '"'

            result = eval(value + self._conditions[name])
            logging.info("Condition evaluated {2}: {0}{1}".format(name,
                                        self._conditions[name], str(result)))

            return result
        else:
            return True

    def _prepare_conditions(self):
        """ Search for var names in conditions """
        varname_r = r"[a-zA-Z_][a-zA-Z0-9_]*"

        conds = self.get_multi_opt("condition")
        logging.debug(conds)
        for cond in conds:
            if cond == None:
                continue
            logging.debug(cond)
            match = re.match(varname_r, cond)
            if match:
                name = match.group(0)
                self._conditions[name] = cond.replace(name, "")
            else:
                raise CommandException(self)


    def run(self):
        self._prepare_conditions()

        setup_name = self.get_mopt("setup")
        logging.info("Started Multicast test setup {0}".format(setup_name))

        cmd = self._compose_cmd()
        data_stdout = self.exec_from("multicast", cmd, die_on_err=False,
                                        log_outputs=False)[0]

        res = {}

        # line format matches name=value pairs with optional
        # double quotes around the value
        line_format_r = r"([a-zA-Z0-9_ ]+)=\"?([a-zA-Z0-9_ ]*)\"?"

        for line in data_stdout.split("\n"):
            match = re.search(line_format_r, line)
            if match:
                name  = match.group(1).strip()
                value = match.group(2).strip()

                res[name] = value
                logging.info("Test result: {0} = {1}".format(name, value))
                if not self._evaluate_result(name, value):
                    return self.set_fail("Conditions not met!", res)

        return self.set_pass(res)
