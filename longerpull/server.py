"""
Longer Pull Server
"""

import aiocluster
import asyncio
from . import protocol


class Server(aiocluster.WorkerService):

    async def start(self, addr='0.0.0.0', port=8001, loop=None):
        if loop is None:
            loop = asyncio.get_event_loop()
        server = await asyncio.start_server(
            protocol.LPServerConnection.on_connect,
            addr, port, reuse_port=True, loop=loop)
        await server.wait_closed()

    def on_connect(self, reader, writer):
        """ Handle new LP connection. """
        conn = protocol.LPServerConnection()
        server = await asyncio.start_server(
            protocol.LPServerConnection.on_connect,
            addr, port, reuse_port=True, loop=loop)
    async def 
