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
    split = intrs.split('\n')
    if len(split) == 1 and split[0] == '':
        # try to get interrupts from msi_irqs directory
        pi = machine.run("dev_irqs=/sys/class/net/%s/device/msi_irqs; "
                         "[ -d $dev_irqs ] && ls -1 $dev_irqs"
                        % device.get_devname())
        res = pi.get_result()
        intrs = res["res_data"]["stdout"]

    for intr in intrs.split('\n'):
        try:
            int(intr)
        except:
            continue
        machine.config("/proc/irq/%s/smp_affinity_list" % intr.strip(), cpu)
