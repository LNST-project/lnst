#!/bin/python

"""
Copyright 2017 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jiri@mellanox.com (Jiri Pirko)
"""

from lnst.Common.Parameters import Param
from lnst.Controller import Controller
from lnst.Controller import BaseRecipe
from TestLib import TestLib
import argparse

class SwitchdevRecipe(BaseRecipe):
    args = Param()

    def __init__(self, **kwargs):
        super(SwitchdevRecipe, self).__init__(**kwargs)
        args = self.params.args
        self.tl = TestLib(mtu=args.mtu)

def run_switchdev_recipe(recipe):
    parser = argparse.ArgumentParser()
    parser.add_argument('--mtu', type=int, default=1500, help='mtu')
    args = parser.parse_args()
    ctl = Controller(debug=1)
    r = recipe(args=args)
    ctl.run(r)
