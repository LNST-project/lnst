"""
This module contains code code for paths and references.

Copyright 2012 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jtluka@redhat.com (Jan Tluka)
"""

import os
from urllib.parse import urljoin
from urllib.request import urlopen
from urllib.error import HTTPError
from tempfile import NamedTemporaryFile

def get_path_class(root, path):
    if root == None:
        if path.startswith('http'):
            return HttpPath(root, path)
        else:
            if os.access(path, os.R_OK):
                return FilePath(None, os.path.realpath(path))
            else:
                raise Exception("Path does not exist \"%s\"!" % path)

    if root.startswith('http'):
        return HttpPath(root, path)
    elif os.access(root, os.R_OK):
        return FilePath(root, path)
    else:
        raise Exception("Could not recognize path type \"%s\"" % path)

class Path:
    def __init__(self, root, path):
        self._path_class = get_path_class(root, path)

    def get_root(self):
        return self._path_class.get_root()

    def abs_path(self):
        return self._path_class.abs_path()

    def to_str(self):
        return self._path_class.to_str()

    def exists(self):
        return self._path_class.exists()

    def resolve(self):
        return self._path_class.resolve()

class PathGeneric:
    def __init__(self, root, path):
        self._root = root
        self._path = path
        self._data = None

    def get_root(self):
        pass

    def abs_path(self):
        pass

    def to_str(self):
        pass

    def exists(self):
        pass

    def resolve(self):
        pass

class FilePath(PathGeneric):
    def _load_file(self):
        f = open(self.abs_path(),'r')
        self._data = f.read()
        f.close()

    def to_str(self):
        if not self._data:
            self._load_file()

        return self._data

    def _append_path(self, path):
        basedir = os.path.dirname(self._path)
        return os.path.join(basedir, path)

    def abs_path(self):
        if self._root:
            return os.path.normpath(os.path.join(self._root,
                                    os.path.expanduser(self._path)))
        else:
            return os.path.normpath(os.path.expanduser(self._path))

    def get_root(self):
        return os.path.dirname(self.abs_path())

    def exists(self):
        return os.path.isfile(self.abs_path())

    def resolve(self):
        return self.abs_path()

class HttpPath(PathGeneric):
    _file = None
    def _get_url(self):
        url = self.abs_path()

        try:
            f = urlopen(url)
            self._data = f.read()
        except IOError as err:
            msg = "Unable to resolve path: %s (%s)" % (url, str(err))
            raise Exception(msg)

        f.close()

    def to_str(self):
        if not self._data:
            self._get_url()

        return self._data

    def abs_path(self):
        if self._root:
            return urljoin(self._root + '/', self._path)
        else:
            return self._path

    def get_root(self):
        url = self.abs_path()
        return url.rpartition('/')[0]

    def exists(self):
        url = self.abs_path()
        try:
            f = urlopen(url)
        except HTTPError:
            return False

        f.close()
        return True

    def resolve(self):
        if self._file:
            return self._file.name

        self._file = NamedTemporaryFile(delete=True)
        self._file.write(self.to_str())
        self._file.flush()

        return self._file.name
