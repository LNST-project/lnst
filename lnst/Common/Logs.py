"""
Utils for logging.

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__autor__ = """
jzupka@redhat.com (Jiri Zupka)
"""
import os, sys, shutil, datetime
from logging import Formatter
import logging.handlers
import traceback
from lnst.Common.LoggingHandler import LogBuffer
from lnst.Common.LoggingHandler import TransmitHandler

def log_exc_traceback():
    cmd_type, value, tb = sys.exc_info()
    exception = traceback.format_exception(cmd_type, value, tb)
    logging.debug(''.join(exception))


class MultilineFormater(Formatter):
    """
    Better formating of multiline logs.
    """
    def __init__(self, fmt=None, datefmt=None, linefmt=None):
        Formatter.__init__(self, fmt, datefmt)
        if linefmt:
            self.linefmt = linefmt
        else:
            self.linefmt = ""

    def format(self, record):
        """
        Format the specified record as text.

        The record's attribute dictionary is used as the operand to a
        string formatting operation which yields the returned string.
        Before formatting the dictionary, a couple of preparatory steps
        are carried out. The message attribute of the record is computed
        using LogRecord.getMessage(). If the formatting string uses the
        time (as determined by a call to usesTime(), formatTime() is
        called to format the event time. If there is exception information,
        it is formatted using formatException() and appended to the message.
        """
        record.message = record.getMessage()
        if not "address" in record.__dict__:
            record.address = "(127.0.0.1)"
        if self._fmt.find("%(asctime)") >= 0:
            record.asctime = self.formatTime(record, self.datefmt)
        lines = record.__dict__["message"].split("\n")
        s = ""
        if len(lines) > 1:
            record.__dict__['message'] = ""
            for line in lines:
                s += "\n" + self.linefmt + line
        s = self._fmt % record.__dict__ + s
        if record.exc_info:
            # Cache the traceback text to avoid converting it multiple times
            # (it's constant anyway)
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            if s[-1:] != "\n":
                s = s + "\n"
            try:
                s = s + record.exc_text
            except UnicodeError:
                # Sometimes filenames have non-ASCII chars, which can lead
                # to errors when s is Unicode and record.exc_text is str
                # See issue 8924
                s = s + record.exc_text.decode(sys.getfilesystemencoding())
        return s
