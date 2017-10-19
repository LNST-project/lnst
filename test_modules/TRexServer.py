"""
T-Rex Server test module
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import os
import sys
import ast
import logging
import yaml
import tempfile
from lnst.Common.TestsCommon import TestGeneric
from lnst.Common.ExecCmd import exec_cmd

class TRexServer(TestGeneric):
    def __init__(self, command):
        super(TRexServer, self).__init__(command)

        self._trex_path = self.get_mopt("trex_path")
        self._trex_config = [ast.literal_eval(self.get_mopt("trex_config"))]

    def run(self):
        cfg_file = tempfile.NamedTemporaryFile(delete=False)
        yaml.dump(self._trex_config, cfg_file)

        exec_cmd("unset TMUX; tmux new-session -d -s trex 'cd {trex_dir}; ./t-rex-64 --cfg {cfg_path} -i'".format(
                 trex_dir=self._trex_path,
                 cfg_path=cfg_file.name))

        self.wait_on_interrupt()

        exec_cmd("unset TMUX; tmux kill-session -t trex")
        os.remove(cfg_file.name)

        res_data = {}
        res_data["msg"] = ""
        return self.set_pass(res_data)
