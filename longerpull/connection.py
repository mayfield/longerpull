"""
Server side protocol (for now).
"""

import collections
import itertools
import json
import logging
import struct
import zlib
from . import commands

logger = logging.getLogger('longerpull')

Preamble = collections.namedtuple('Preamble', 'size, ident, use_zlib')


class LPConnection(object):

    __slots__ = (
    )
    version = 1
    chksum_magic = 194
    #identer = itertools.count()
    preamble = struct.Struct("!BBIIB")

    def chksum(self, value):
        return self.chksum_magic ^ ((value & 0xff) ^ 0xff)

    def encode(self, ident, value):
        data = json.dumps(value).encode()
        size = len(data)
        #ident = next(self.identer)
        chksum = self.chksum(size + ident)
        preamble = self.preamble.pack(self.version, chksum, size, ident, 0)
        return preamble + data

    def decode_preamble(self, data):
        print(len(data))
        ver, chksum, size, ident, use_zlib = self.preamble.unpack(data)
        if ver != 1:
            raise TypeError('unsupported version')
        elif chksum != self.chksum(size + ident):
            raise ValueError('chksum error')
        return Preamble(size, ident, not not use_zlib)

    def decode_message(self, data, use_zlib):
        if use_zlib:
            data = zlib.decompress(data)
        return json.loads(data.decode())


class LPServerConnection(LPConnection):

    __slots__ = (
        'reader',
        'writer',
        'commands',
    )

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.commands = {
            'authorize': self.authorize_command,
            'check_activation': self.check_activation_command
        }

    @classmethod
    async def on_connect(cls, reader, writer):
        instance = cls(reader, writer)
        while await instance.parse_command():
            pass

    async def parse_command(self):
        print('PAS', self.preamble.size)
        data = await self.reader.read(self.preamble.size)
        if not data:
            return False  # connection closed
        preamble = self.decode_preamble(data)
        data = await self.reader.read(preamble.size)
        logger.debug("Parsing Command: %s size:%d zlib:%s" % (preamble.ident,
                     preamble.size, preamble.use_zlib))
        msg = self.decode_message(data, preamble.use_zlib)
        handler = self.commands[msg['command']]
        resp = await handler(**msg['args'])
        print(resp)
        self.writer.write(self.encode(preamble.ident, resp))
        await self.writer.drain()
        return True


    async def authorize_command(self, *, username=None, password=None):
        pass
