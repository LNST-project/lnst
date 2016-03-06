"""
Copyright 2016 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
idosch@mellanox.com (Ido Schimmel)
"""

from lnst.Controller.Task import ctl
from TestLib import TestLib
from time import sleep

def linkneg(tl, if1, if2):
    if1_drv = str(if1.get_driver())
    if2_drv = str(if2.get_driver())

    # The mlx5_core upstream driver is currently buggy and does not support
    # link negotiation. Patches were sent to the NIC team.
    if 'mlx5' in if1_drv or 'mlx5' in if2_drv:
        return

    if 'mlx4' in if1_drv or 'mlx4' in if2_drv:
        speeds = [10000, 40000]
    else:
        speeds = [10000, 40000, 100000]

    for speed in speeds:
        tl.linkneg(if1, if2, True, speed=speed, timeout=30)
        tl.ping_simple(if1, if2)

def do_task(ctl, hosts, ifaces, aliases):
    m1, sw = hosts
    m1_if1, m1_if2, m1_if3, m1_if4, sw_if1, sw_if2, sw_if3, sw_if4 = ifaces

    m1_if1.reset(ip=["192.168.101.10/24", "2002::1/64"])
    m1_if2.reset(ip=["192.168.102.10/24", "2003::1/64"])
    m1_if3.reset(ip=["192.168.103.10/24", "2004::1/64"])
    m1_if4.reset(ip=["192.168.104.10/24", "2005::1/64"])
    sw_if1.reset(ip=["192.168.101.11/24", "2002::2/64"])
    sw_if2.reset(ip=["192.168.102.11/24", "2003::2/64"])
    sw_if3.reset(ip=["192.168.103.11/24", "2004::2/64"])
    sw_if4.reset(ip=["192.168.104.11/24", "2005::2/64"])

    sleep(30)

    tl = TestLib(ctl, aliases)

    for (if1, if2) in [(sw_if1, m1_if1), (sw_if2, m1_if2), (sw_if3, m1_if3),
                       (sw_if4, m1_if4)]:
        linkneg(tl, if1, if2)
        linkneg(tl, if2, if1)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine1").get_interface("if2"),
         ctl.get_host("machine1").get_interface("if3"),
         ctl.get_host("machine1").get_interface("if4"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2"),
         ctl.get_host("switch").get_interface("if3"),
         ctl.get_host("switch").get_interface("if4")],
        ctl.get_aliases())
