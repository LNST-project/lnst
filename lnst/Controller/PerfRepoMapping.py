"""
This module defines the PerfRepoMapping class that is used as an interface to
mapping files that map recipe keys to IDs in a PerfRepo instance.

Copyright 2015 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import re
import logging
import pprint
from lnst.Common.Path import Path

class PerfRepoMapping(object):
    def __init__(self, filepath):
        if not isinstance(filepath, Path):
            filepath = Path(None, filepath)

        self._filepath = filepath.resolve()
        self._mapping = {}
        self.load_mapping_file(self._filepath)

    def load_mapping_file(self, filename):
        line_re = re.compile(r"^(\w+)\s*=\s*(\w+)\s*$")
        res_dict = {}

        lines = []
        try:
            with open(filename) as f:
                lines = f.readlines()
        except:
            self._mapping = {}
            raise

        lines = self._preprocess_lines(lines)

        for line in lines:
            match = line_re.match(line)
            if match is not None and len(match.groups()) == 2:
                h = match.group(1)
                if h in res_dict:
                    logging.warn("Duplicate entry found for hash: %s\n"
                                 "\t %s = %s (previous)\n"
                                 "\t %s (new)" % (h, h, res_dict[h], line))
                res_dict[h] = match.group(2)
            else:
                logging.warn("Skipping mapping line, invalid format:\n%s" %line)
        self._mapping = res_dict

    def _preprocess_lines(self, lines):
        comment_re = re.compile(r"^(.*?)#.*$")
        result_lines = []

        for line in lines:
            line = line.strip()
            match = comment_re.match(line)
            if match and len(match.groups()) == 1:
                line = match.group(1)
            line = line.strip()
            if line != "":
                result_lines.append(line)
        return result_lines

    def get_id(self, key):
        try:
            return self._mapping[key]
        except (KeyError, TypeError):
            return None

    def __str__(self):
        if self._mapping is None:
            return ""
        else:
            return pprint.pformat(self._mapping)
