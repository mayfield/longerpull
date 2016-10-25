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

    __slots__ = (
        '_loop',
        '_paused',
        '_recv_queue',
        '_recv_waiter',
        '_server',
        'ident',
        'poll_id',
        'protocol',
    )
    _identer = itertools.count()
    _pause_threshold = 1

    def __init__(self, connect_waiter, server=None, loop=None):
        self._recv_waiter = None
        self._recv_queue = None#collections.deque()
        self._server = server
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

    def feed_message(self, msg_id, data, is_compressed):
        """ Decode and deliver (or enqueue) a message from the client.  The
        transport calls this function once it has enough data gathered to
        feed a whole message. If our queue is too full the transport is asked
        to pause until it is sufficiently drained by `recv_message()`. """
        msgtuple = msg_id, self.decode_message(data, is_compressed)
        if self._recv_waiter is None:
            self._server.conn_recv_enqueue += 1
            if self._recv_queue is None:
                self._recv_queue = collections.deque()
            self._recv_queue.append(msgtuple)
            if not self._paused and \
               len(self._recv_queue) >= self._pause_threshold:
                self.pause_transport()
        else:
            self._server.conn_recv_direct += 1
            f = self._recv_waiter
            self._recv_waiter = None
            f.set_result(msgtuple)

    def feed_exception(self, exc):
        if self._recv_waiter is None:
            if self._recv_queue is None:
                self._recv_queue = collections.deque()
            self._recv_queue.append(exc)
        else:
            f = self._recv_waiter
            self._recv_waiter = None
            f.set_exception(exc)

    def recv_message(self):
        assert self._recv_waiter is None
        f = self._loop.create_future()
        if self._recv_queue is not None:
            self._server.conn_recv_dequeue += 1
            f.set_result(self._recv_queue.popleft())
            if not self._recv_queue:
                self._recv_queue = None
        else:
            self._server.conn_recv_wait += 1
            self._recv_waiter = f
        if self._paused and self._recv_queue is None:
            self.resume_transport()
        return f

    def pause_transport(self):
        logger.debug('Pausing: %s' % self)
        self.protocol.transport.pause_reading()
        self._server.conn_pause_count += 1
        self._paused = True

    def resume_transport(self):
        logger.debug('Resuming: %s' % self)
        self.protocol.transport.resume_reading()
        self._paused = False

    def encode_message(self, value):
        is_compressed = True
        data = ujson.dumps(value, ensure_ascii=False).encode()
        return zlib.compress(data), is_compressed

    def decode_message(self, data, is_compressed):
        if is_compressed:
            data = zlib.decompress(data)
        else:
            data = data.tobytes()
        return ujson.loads(data)

    def send_message(self, msg_id, msg):
        data, is_compressed = self.encode_message(msg)
        preamble = _protocol.encode_preamble(msg_id, data, is_compressed)
        self.protocol.transport.write(preamble + data)

    def close(self):
        return self.protocol.transport.close()


class LPProtocol(object):

    __slots__ = (
        '_buffer',
        '_conn',
        '_connect_waiter',
        '_is_compressed',
        '_msg_id',
        '_waiting_bytes',
        'state',
        'transport',
    )
    version = 1
    _preamble_size = 10
    _states = enum.Enum('States', 'connect preamble data closed')

    def __init__(self, connection, connect_waiter):
        self._conn = connection
        self._connect_waiter = connect_waiter
        self.transport = None
        super().__init__()

    def connection_made(self, transport):
        self.transport = transport
        self.state = self._states.connect
        self._buffer = None
        self._waiting_bytes = 1
        self._msg_id = 0
        self._is_compressed = None
        waiter = self._connect_waiter
        self._connect_waiter = None
        waiter.set_result(self._conn)

    def data_received(self, data):
        if self._buffer is not None:
            self._buffer.extend(data)
            data = self._buffer
            self._buffer = None
        view = memoryview(data)
        while len(view) >= self._waiting_bytes:
            block = view[:self._waiting_bytes]
            view = view[self._waiting_bytes:]
            if self.state is self._states.preamble:
                self._waiting_bytes, self._msg_id, self._is_compressed = \
                    _protocol.decode_preamble(block)
                self.state = self._states.data
            elif self.state is self._states.data:
                self._conn.feed_message(self._msg_id, block, self._is_compressed)
                self._waiting_bytes = self._preamble_size
                self.state = self._states.preamble
            elif self.state is self._states.connect:
                version = block[0]
                if version != self.version:
                    raise BadVersion('Unsupported version: %d' % version)
                self._waiting_bytes = self._preamble_size
                self.state = self._states.preamble
        if view:
            self._buffer = bytearray(view)

    def connection_lost(self, exc):
        conn = self._conn
        self._conn = None
        if exc is None:
            try:
                raise ConnectionLost()
            except ConnectionLost as e:
                exc = e
        conn.feed_exception(exc)

    def eof_received(self):
        pass

    def pause_writing(self):
        pass

    def resume_writing(self):
        pass
