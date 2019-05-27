"""
Module containing just the version number of the package, needs to be separated
to avoid dependency resolution conflicst during setup.py execution.

Copyright 2016 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

try:
    from lnst.Common.GitVersion import git_version
except ImportError:
    git_version = None

class LNSTVersion(object):
    def __init__(self):
        self._version = "14"

        if git_version:
            self._version += "-" + git_version().decode()

    @property
    def version(self):
        return self._version

    @property
    def is_git_version(self):
        return git_version is not None

    def __str__(self):
        return str(self.version)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return str(self) == str(other)
        return NotImplemented

    def __ne__(self, other):
        res = self == other
        if res is not NotImplemented:
            return not res
        return NotImplemented

lnst_version = LNSTVersion()
