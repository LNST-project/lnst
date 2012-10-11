"""
This package provides a useful wrapper around the xmlrpc client and server
from stdlib. The main benefits include:

The server provides functions alive and kill. More over, any exception generated
in rpc functions result in the whole stack trace to be sent across. The client
processes this stack trace and re-raises the exception.

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.

Copyright 2008 Raghuram Devarakonda <draghuram@gmail.com>
Adapted by Red Hat with the author's permission from:
http://www.mail-archive.com/python-list@python.org/msg207800.html
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

from SimpleXMLRPCServer import SimpleXMLRPCServer
from Common.Logs import log_exc_traceback
import xmlrpclib
import sys
import socket
import SocketServer
import traceback

# All public methods in this class are callable by clients.
class UtilityFuncs(object):
    def __init__(self, *args, **kwargs):
        self.running = True

    def kill(self):
        self.running = False
        return True

    def alive(self):
        return True

class Server(SimpleXMLRPCServer):
    def __init__(self, *args, **kwargs):
        self.util_inst = UtilityFuncs()
        SimpleXMLRPCServer.__init__(self, *args, **kwargs)
        self.register_instance(self.util_inst)

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        SimpleXMLRPCServer.server_bind(self)

    '''
    The default dispatcher does not send across the whole stacktrace.
    Only type and value are passed back. The client has no way of knowing
    the exact place where error occurred in the server (short of some
    other means such as server logging). This dispatcher sends the whole
    stack trace.
    '''
    def _dispatch(self, method, params):
        try:
            return SimpleXMLRPCServer._dispatch(self, method, params)
        except Exception as err:
            log_exc_traceback()
            raise xmlrpclib.Fault(1, str(err))

    def serve_until_done(self):
        while self.util_inst.running:
            self.handle_request()

'''
A special exception has been defined just to indicate in the client
that the exception has in fact originated on the server.
'''

class ServerException(Exception):
    pass

'''
The server sends the whole stack trace as a string. Convert it back to
an exception here.
'''

class ExceptionUnmarshaller(xmlrpclib.Unmarshaller):
    def close(self):
        try:
            return xmlrpclib.Unmarshaller.close(self)
        except xmlrpclib.Fault, e:
            raise ServerException(e.faultString)

class ExceptionTransport(xmlrpclib.Transport):
    '''
    getparser() in xmlrpclib.Transport has logic to choose fastest parser
    available. The parser needs to be passed an unmarshaller. Unfortunately,
    getparser() there does not take unmarshaller as a parameter so we
    can not simply call it with our unmarshaller. Either the whole code
    there needs to be replicated here using our unmarshaller or we use
    a much simpler version. The latter is chosen (partly because the code is
    inspired by ASPN recipe 365244.
    '''
    def getparser(self):
        unmarshaller = ExceptionUnmarshaller()
        parser = xmlrpclib.ExpatParser(unmarshaller)
        return parser, unmarshaller

class ServerProxy(xmlrpclib.ServerProxy):
    def __init__ (self, *args, **kwargs):
        '''
        Supply our own transport
        '''
        try:
            kwargs['transport']
        except:
            # This is expected
            pass
        else:
            raise Exception('A transport (%s) is provided. This is not '
                            'expected as a custom transport is being used'
                                                    % kwargs['transport'])

        kwargs['transport'] = ExceptionTransport()
        xmlrpclib.ServerProxy.__init__(self, *args, **kwargs)
