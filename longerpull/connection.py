"""
Server side protocol (for now).
"""

import itertools
import logging
import struct
import ujson
import zlib
from . import _protocol

logger = logging.getLogger('lp.conn')


class ConnectionException(Exception):
    pass


class BadVersion(ConnectionException):
    pass


class LPConnection(object):

    __slots__ = (
        'reader',
        'writer'
    )
    version = 1
    _identer = itertools.count()
    _preamble_size = 10

    def __init__(self, reader, writer):
        self.ident = next(self._identer)
        self.reader = reader
        self.writer = writer
        self.peername = '%s:%d' % writer.get_extra_info('socket').getpeername()

    def __str__(self):
        return '<%s [%s] ident:%d>' % (type(self).__qualname__, self.peername,
                                       self.ident)

    def encode_message(self, value):
        is_compressed = True
        data = ujson.dumps(value, ensure_ascii=False).encode()
        return zlib.compress(data), is_compressed

    def decode_message(self, data, is_compressed):
        if is_compressed:
            data = zlib.decompress(data)
        return ujson.loads(data)

    def close(self):
        self.writer.close()


class LPServerConnection(LPConnection):

    async def check_version(self):
        # read() is safe since it must return > 0 bytes and we only need 1.
        version = (await self.reader.read(1))[0]
        if version != self.version:
            raise BadVersion('Unsupported version: %d' % version)

    async def recv(self):
        """ Read preamble and then full message data from reader stream.
        Parse the message and return a tuple of the msg id and message
        value. """
        data = await self.reader.readexactly(self._preamble_size)
        size, msg_id, is_compressed = _protocol.decode_preamble(data)
        data = await self.reader.readexactly(size)
        message = self.decode_message(data, is_compressed)
        return msg_id, message

    def send(self, msg_id, message):
        """ Send a message/reply to the client. """
        data, is_compressed = self.encode_message(message)
        preamble = _protocol.encode_preamble(msg_id, data, is_compressed)
        self.writer.write(preamble + data)
