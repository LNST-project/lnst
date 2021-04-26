"""
Custom logging handlers we use.

LogBuffer
Handler used solely for temporarily storing messages so that they can be
retrieved later.

Copyright 2012 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import pickle
import logging
import xmlrpc.client
from lnst.Common.ConnectionHandler import send_data

class LogBuffer(logging.Handler):
    """
    Handler used for buffering log messages. Compared to the BufferingHandler
    defined in Python it doesn't have a capacity. It is intended to be used
    solely as a temporary storage of logged messages so that they can be later
    retrieved.
    """
    def __init__(self):
        logging.Handler.__init__(self)
        self.buffer = []

    def makePickle(self, record):
        """
        Pickles the record so that it can be sent over the xmlrpc we use.
        """
        d = dict(record.__dict__)
        d['msg'] = record.getMessage()
        d['args'] = None
        d['exc_info'] = None
        s = pickle.dumps(d, 1)
        return xmlrpc.client.Binary(s)

    def add_buffer(self, buf):
        for i in buf:
            self.buffer.append(i)

    def emit(self, record):
        s = self.makePickle(record)
        self.buffer.append(s)

    def flush(self):
        self.acquire()

        buf = list(self.buffer)
        self.buffer = []

        self.release()
        return buf

    def close(self):
        self.flush()
        logging.Handler.close(self)

class TransmitHandler(logging.Handler):
    def __init__(self, target):
        logging.Handler.__init__(self)
        self.target = target
        self._origin_name = None

    def set_origin_name(self, name):
        self._origin_name = name

    def emit(self, record):
        r = dict(record.__dict__)
        r['msg'] = record.getMessage()
        r['args'] = None
        r['exc_info'] = None
        if self._origin_name != None:
            r['origin_name'] = self._origin_name

        data = {"type": "log", "record": r}

        send_data(self.target, data)

    def close(self):
        logging.Handler.close(self)


class ExportHandler(logging.Handler):
    def __init__(self, logs):
        logging.Handler.__init__(self)
        self._log_list = logs

    def emit(self, record):
        self._log_list.append(record)

    def close(self):
        logging.Handler.close(self)
