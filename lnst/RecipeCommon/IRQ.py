"""
This module defines the functions for IRQ tuning that can be imported
directly into LNST Python tasks.

Copyright 2015 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jtluka@redhat.com (Jan Tluka)
"""


'''
Pins all device IRQs to specified cpu on machine.

machine: HostAPI object
device: InterfaceAPI object
cpu: integer
'''
def pin_dev_irqs(machine, device, cpu):
    pi = machine.run("grep %s /proc/interrupts | cut -f1 -d: | sed 's/ //'"
                    % device.get_devname())
    res = pi.get_result()
    intrs = res["res_data"]["stdout"]
    for intr in intrs.split('\n'):
        try:
            int(intr)
        except:
            continue
        machine.config("/proc/irq/%s/smp_affinity_list" % intr.strip(), cpu)
