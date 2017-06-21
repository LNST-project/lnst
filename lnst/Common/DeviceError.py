"""
Defines the DeviceError, DeviceDeleted and DeviceNotFound exceptions.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Common.LnstError import LnstError

class DeviceError(LnstError):
    pass

class DeviceDeleted(DeviceError):
    pass

class DeviceNotFound(DeviceError):
    pass

class DeviceConfigError(DeviceError):
    pass

class DeviceConfigValueError(DeviceConfigError):
    pass
