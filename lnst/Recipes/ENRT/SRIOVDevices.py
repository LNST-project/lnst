from dataclasses import dataclass
from itertools import zip_longest
from typing import Optional

from lnst.Devices import RemoteDevice


@dataclass
class SRIOVDevices():
    """
    The class takes care of
    1. creating the vfs
    2. accessing the vfs by index or using next()
    3. accessing the vf representors by index or using next()
    3. accessing vf/vf representor pairs by index or using next()

    For example:
    ```
    host.eth0.eswitch_mode = "switchdev"
    sriov_devices = SRIOVDevices(host.eth0, 2)

    vfs = sriov_devices.vfs # all vf devices
    vf_representors = sriov_devices.vf_reps # all vf representors

    vf0, vf_rep0 = sriov_devices[0] # vf/vf_rep of first virtual function
    vf1, vf_rep1 = sriov_devices[1] # vf/vf_rep of second virtual function

    for vf, vf_rep in sriov_devices: # iteration over vf/vf_representor pairs
        vf.up()
        vf_rep.up()
    ```
    """
    phys_dev: RemoteDevice
    vfs: list[RemoteDevice]
    vf_reps: Optional[list[RemoteDevice]] = None

    def __init__(self, phys_dev: RemoteDevice, number_of_vfs: int = 1):
        self.phys_dev = phys_dev
        phys_dev.up_and_wait()
        self.vfs, self.vf_reps = phys_dev.create_vfs(number_of_vfs)

        for vf_index, vf in enumerate(self.vfs):
            phys_dev.host.map_device(f"{phys_dev._id}_vf{vf_index}", {"ifname": vf.name})

        if self.vf_reps is not None:
            for vf_rep_index, vf_rep in enumerate(self.vf_reps):
                phys_dev.host.map_device(f"{phys_dev._id}_vf_rep{vf_rep_index}", {"ifname": vf_rep.name})

    def __iter__(self):
        if self.vf_reps:
            return zip(self.vfs, self.vf_reps, strict=True)

        return zip_longest(self.vfs, [None])

    def __getitem__(self, key):
        if self.vf_reps:
            return self.vfs[key], self.vf_reps[key]

        return self.vfs[key], None
