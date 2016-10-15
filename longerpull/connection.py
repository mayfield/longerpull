"""
Server side protocol (for now).
"""

import itertools
import ujson as json
import logging
import struct
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
    chksum_magic = 194
    preamble = struct.Struct("!BIIB")
    identer = itertools.count()

    def __init__(self, reader, writer):
        self.ident = next(self.identer)
        self.reader = reader
        self.writer = writer
        self.peername = '%s:%d' % writer.get_extra_info('socket').getpeername()
        self.encode_preamble = _protocol.encode_preamble
        self.decode_preamble = _protocol.decode_preamble

    def __str__(self):
        return '<%s [%s] ident:%d>' % (type(self).__qualname__, self.peername,
                                       self.ident)

    def chksum(self, value):
        return self.chksum_magic ^ ((value & 0xff) ^ 0xff)

    def encode_message(self, value):
        is_compressed = False
        data = json.dumps(value).encode()
        return data, is_compressed

    def encode_preamble(self, msg_id, size, is_compressed):
        size += 1  # size includes the compression byte.
        chksum = self.chksum(size + msg_id)
        return self.preamble.pack(chksum, size, msg_id, is_compressed)

    def decode_preamble(self, data):
        chksum, size, msg_id, is_compressed = self.preamble.unpack(data)
        if chksum != self.chksum(size + msg_id):
            raise ValueError('chksum error')
        return size, msg_id, not not is_compressed

    def decode_message(self, data, is_compressed):
        if is_compressed:
            data = zlib.decompress(data)
        return json.loads(data.decode())

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
        data = await self.reader.readexactly(self.preamble.size)
        size, msg_id, is_compressed = self.decode_preamble(data)
        data = await self.reader.readexactly(size - 1)
        message = self.decode_message(data, is_compressed)
        return msg_id, message

    def send(self, msg_id, message, drain=True):
        """ Send a message/reply to the client. """
        data, is_compressed = self.encode_message(message)
        preamble = self.encode_preamble(msg_id, len(data), is_compressed)
        self.writer.write(preamble + data)
