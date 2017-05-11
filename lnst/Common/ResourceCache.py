"""

Copyright 2012 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import logging
import os
import re
import time
import shutil
import json
from lnst.Common.ExecCmd import exec_cmd
from lnst.Common.Utils import sha256sum
from lnst.Common.LnstError import LnstError

#current index version
INDEX_VERSION = 1
#minimal supported index version -- will be updated to current one when loaded
MIN_INDEX_VERSION = 1

class ResourceCacheError(LnstError):
    pass

class ResourceCache(object):
    _CACHE_INDEX_FILE_NAME = "index"
    _root = None
    _expiration_period = None

    def __init__(self, cache_path, expiration_period):
        if os.path.exists(cache_path):
            if os.path.isdir(cache_path):
                self._root = cache_path
            else:
                raise ResourceCacheError("Invalid cache path (%s)" % cache_path)
        else:
            os.makedirs(cache_path)
            self._root = cache_path

        self._index = {"index_version": INDEX_VERSION,
                       "entries": {}}
        self._read_index()
        self._expiration_period = expiration_period

    def _read_index(self):
        try:
            with open(self.index_path, "w") as f:
                index = json.load(f)
                if index["index_version"] > INDEX_VERSION:
                    raise ResourceCacheError("Incompatible ResourceCache index versions")
                elif index["index_version"] == INDEX_VERSION:
                    self._index = index
                    logging.debug("Resource cache index loaded")
                else:
                    self._index = self._update_old_index(index)
                    logging.debug("Resource cache index loaded")
                    self._save_index()
        except:
            pass

    def _update_old_index(self, old):
        if old["index_version"] < MIN_INDEX_VERSION:
            raise ResourceCacheError("ResourceCache index version too old to update")
        logging.debug("Updating old index to newer version")
        return old

    def _save_index(self):
        with open(self.index_path, "w") as f:
            json.dump(self._index, f)
            logging.debug("Resource cache index commited")

    @property
    def index_path(self):
        return "%s/%s" % (self.root, self._CACHE_INDEX_FILE_NAME)

    @property
    def root(self):
        return self._root

    def query(self, res_hash):
        return res_hash in self._index["entries"]

    def get_path(self, res_hash):
        return self._index["entries"][res_hash]["path"]

    def renew_entry(self, entry_hash):
        self._index["entries"][entry_hash]["last_used"] = int(time.time())
        self._save_index()

    def add_file_entry(self, filepath, entry_name):
        entry_hash = sha256sum(filepath)

        if entry_hash in self._index["entries"]:
            raise ResourceCacheError("File already in cache")

        entry_path = "%s/%s" % (self._root, entry_hash)
        if os.path.exists(entry_path):
            os.remove(entry_path)

        shutil.move(filepath, entry_path)

        entry = {"name": entry_name,
                 "path": entry_path,
                 "last_used": int(time.time()),
                 "digest": entry_hash,
                 "type": "file"}
        self._index["entries"][entry_hash] = entry

        self._save_index()

        return entry_hash

    def del_cache_entry(self, entry_hash):
        if entry_hash in self._index["entries"]:
            os.remove(self._index["entries"][entry_hash].path)
            del self._index["entries"][entry_hash]
            self._save_index()

    def del_old_entries(self):
        if self._expiration_period == 0:
            return

        rm = []
        now = time.time()
        for entry_hash, entry in self._index["entries"].iteritems():
            if entry["last_used"] <= (now - self._expiration_period):
                rm.append(entry_hash)

        for entry_hash in rm:
            self.del_cache_entry(entry_hash)
