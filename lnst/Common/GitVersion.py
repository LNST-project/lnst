"""
Module that calculates the LNST version based on the currently checked-out git
commit. Overrides the default LNST version that is reported when LNST is
installed on the machine with setup.py which skips this module.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import os
import subprocess
from lnst.Common.LnstError import LnstError
from lnst.Common.Utils import is_installed

def git_version():
    if not is_installed("git"):
        raise LnstError("git not installed, can't check for version")

    with open(os.devnull, 'w') as null:
        cwd = os.getcwd()
        abspath = os.path.abspath(__file__)
        dname = os.path.dirname(abspath)
        os.chdir(dname)

        cmd = ['git', 'rev-parse', 'HEAD']
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=null)
            return proc.communicate()[0].decode().strip()
        finally:
            os.chdir(cwd)
