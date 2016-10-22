"""
Server side protocol
"""

import asyncio
import collections
import enum
import itertools
import logging
import ujson
import zlib
from . import _protocol

logger = logging.getLogger('lp.proto')


class ConnectionException(Exception):
    pass


class BadVersion(ConnectionException):
    pass


class ConnectionLost(ConnectionException):
    pass


class LPConnection(object):

    _identer = itertools.count()
    _pause_threshold = 2
    _resume_threshold = 0

    def __init__(self, connect_waiter, loop=None):
        self._recv_waiter = None
        self._recv_queue = collections.deque()
        self._loop = loop
        self._paused = False
        self.ident = next(self._identer)
        self.protocol = LPProtocol(self, connect_waiter)

    def __str__(self):
        if self.protocol.transport is not None:
            tp = self.protocol.transport
            peername = '%s:%d' % tp.get_extra_info('peername')
        else:
            peername = 'unconnected'
        return '<%s [%s] ident:%d>' % (type(self).__name__, peername,
            self.ident)

    def feed_message(self, msg):
        if self._recv_waiter is None:
            self._recv_queue.append(msg)
            if not self._paused and \
               len(self._recv_queue) >= self._pause_threshold:
                #logger.warning("Pausing: %s" % self)
                self.protocol.transport.pause_reading()
                self._paused = True
        else:
            f = self._recv_waiter
            self._recv_waiter = None
            f.set_result(msg)

    def feed_exception(self, exc):
        if self._recv_waiter is None:
            self._recv_queue.append(exc)
        else:
            f = self._recv_waiter
            self._recv_waiter = None
            f.set_exception(exc)

    def recv_message(self):
        assert self._recv_waiter is None
        f = self._loop.create_future()
        if self._recv_queue:
            msg = self._recv_queue.popleft()
            if self._paused and len(self._recv_queue) < self._resume_threshold:
                self.protocol.transport.resume_reading()
                self._paused = False
            f.set_result(msg)
        else:
            if self._paused and self._resume_threshold == 0:
                self.protocol.transport.resume_reading()
                self._paused = False
            self._recv_waiter = f
        return f

    def send_message(self, msg_id, msg):
        data = self.protocol.create_message(msg_id, msg)
        self.protocol.transport.write(data)

    def close(self):
        return self.protocol.transport.close()


class LPProtocol(asyncio.Protocol):

    version = 1
    _preamble_size = 10
    _states = enum.Enum('States', 'connect preamble data closed')

    def __init__(self, connection, connect_waiter):
        self._conn = connection
        self._connect_waiter = connect_waiter
        self.transport = None
        super().__init__()

    def encode_message(self, value):
        is_compressed = True
        data = ujson.dumps(value, ensure_ascii=False).encode()
        return zlib.compress(data), is_compressed

    def decode_message(self, data, is_compressed):
        if is_compressed:
            data = zlib.decompress(data)
        return ujson.loads(data)

    def create_message(self, msg_id, message):
        """ Create a complete binary message ready to be sent. """
        data, is_compressed = self.encode_message(message)
        preamble = _protocol.encode_preamble(msg_id, data, is_compressed)
        return preamble + data

    def connection_made(self, transport):
        self.transport = transport
        self.state = self._states.connect
        self._buffer = bytearray()
        self._waiting_bytes = 1
        self._msg_id = 0
        self._is_compressed = None
        # XXX
        #logger.info('Connected: %s' % self._conn)
        waiter = self._connect_waiter
        self._connect_waiter = None
        waiter.set_result(self._conn)

    def data_received(self, data):
        buf = self._buffer
        buf.extend(data)
        while len(buf) >= self._waiting_bytes:
            data = buf[:self._waiting_bytes]
            del buf[:self._waiting_bytes]
            if self.state is self._states.preamble:
                self._waiting_bytes, self._msg_id, self._is_compressed = \
                    _protocol.decode_preamble(data)
                self.state = self._states.data
            elif self.state is self._states.data:
                message = self.decode_message(bytes(data), self._is_compressed)
                msg_id = self._msg_id
                self._is_compressed = None
                self._msg_id = None
                self._waiting_bytes = self._preamble_size
                self.state = self._states.preamble
                self._conn.feed_message((msg_id, message))
            elif self.state is self._states.connect:
                version = data[0]
                if version != self.version:
                    raise BadVersion('Unsupported version: %d' % version)
                self.state = self._states.preamble
                self._waiting_bytes = self._preamble_size

    def connection_lost(self, exc):
        conn = self._conn
        self._conn = None
        if exc is None:
            try:
                raise ConnectionLost()
            except ConnectionLost as e:
                exc = e
        conn.feed_exception(exc)
