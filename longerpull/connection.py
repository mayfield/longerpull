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

Preamble = collections.namedtuple('Preamble', 'size, cmd_id, use_zlib')


class ConnectionException(Exception):
    pass


class Disconnected(ConnectionException):
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

    def encode(self, cmd_id, value):
        use_zlib = False  # TODO: eval pros/cons
        data = json.dumps(value).encode()
        size = len(data)
        chksum = self.chksum(size + cmd_id)
        preamble = self.preamble.pack(chksum, size, cmd_id, use_zlib)
        return preamble + data

    def decode_preamble(self, data):
        chksum, size, cmd_id, use_zlib = self.preamble.unpack(data)
        if chksum != self.chksum(size + cmd_id):
            print(chksum, size, cmd_id, use_zlib, self.chksum(size+cmd_id))
            raise ValueError('chksum error')
        return Preamble(size, cmd_id, not not use_zlib)

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
        data = await self.reader.read(self.preamble.size)
        if not data:
            raise Disconnected()
        preamble = self.decode_preamble(data)
        data = await self.reader.read(preamble.size)
        logger.debug("Parsing Command: %s size:%d zlib:%s" % (preamble.cmd_id,
                     preamble.size, preamble.use_zlib))
        return preamble.cmd_id, self.decode_message(data, preamble.use_zlib)

    async def send(self, cmd_id, value, drain=True):
        """ Send a message/reply to the client. """
        self.writer.write(self.encode(cmd_id, value))
        if drain:
            await self.writer.drain()
