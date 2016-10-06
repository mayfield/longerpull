"""
Server side protocol (for now).
"""

import collections
import itertools
import json
import logging
import struct
import zlib

logger = logging.getLogger('lp.conn')

Preamble = collections.namedtuple('Preamble', 'size, msg_id, use_zlib')


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

    def __str__(self):
        return '<%s [%s] ident:%d>' % (type(self).__qualname__, self.peername,
                                       self.ident)

    def chksum(self, value):
        return self.chksum_magic ^ ((value & 0xff) ^ 0xff)

    def encode(self, msg_id, value):
        use_zlib = 0  # TODO: eval pros/cons
        data = json.dumps(value).encode()
        size = len(data) + 1  # size includes the compression byte.
        chksum = self.chksum(size + msg_id)
        preamble = self.preamble.pack(chksum, size, msg_id, use_zlib)
        return preamble + data

    def decode_preamble(self, data):
        chksum, size, msg_id, use_zlib = self.preamble.unpack(data)
        if chksum != self.chksum(size + msg_id):
            print(chksum, size, msg_id, use_zlib, self.chksum(size+msg_id))
            raise ValueError('chksum error')
        return Preamble(size, msg_id, not not use_zlib)

    def decode_message(self, data, use_zlib):
        if use_zlib:
            data = zlib.decompress(data)
        return json.loads(data.decode())

    def close(self):
        self.writer.close()


class LPServerConnection(LPConnection):

    async def check_version(self):
        version = (await self.reader.read(1))[0]
        if version != self.version:
            raise BadVersion('Unsupported version: %d' % version)

    async def recv(self):
        """ Read preamble and then full message data from reader stream.
        Parse the message and return a tuple of the msg id and message
        value. """
        data = await self.reader.readexactly(self.preamble.size)
        preamble = self.decode_preamble(data)
        data = await self.reader.readexactly(preamble.size - 1)
        logger.debug("Parsing Message: %s size:%d zlib:%s" % (preamble.msg_id,
                     preamble.size, preamble.use_zlib))
        message = self.decode_message(data, preamble.use_zlib)
        logger.debug("recv: msg_id:%d %s" % (preamble.msg_id, message))
        return preamble.msg_id, message

    async def send(self, msg_id, message, drain=True):
        """ Send a message/reply to the client. """
        logger.debug("send: msg_id:%d %s" % (msg_id, message))
        self.writer.write(self.encode(msg_id, message))
        if drain:
            await self.writer.drain()
