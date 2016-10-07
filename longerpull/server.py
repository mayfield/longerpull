"""
Longer Pull Server
"""

import aiocluster
import asyncio
import logging
from . import connection, commands, rpc

logger = logging.getLogger('lp.server')


class Server(aiocluster.WorkerService):

    def __init__(self, *args, **kwargs):
        self.connections = set()
        super().__init__(*args, **kwargs)

    async def start(self, addr='0.0.0.0', port=8001):
        server = await asyncio.start_server(self.on_connect, addr, port,
                                            reuse_port=True, loop=self.loop)
        await server.wait_closed()

    def on_connect(self, reader, writer):
        """ Handle new LP connection. """
        conn = connection.LPServerConnection(reader, writer)
        self.connections.add(conn)
        t = self.loop.create_task(self.monitor_connection(conn))
        t.conn = conn
        t.add_done_callback(self.on_finish)

    async def monitor_connection(self, conn):
        logger.warning("Connected: %s" % conn)
        try:
            await conn.check_version()
        except connection.BadVersion as e:
            logger.warning(e)
            return
        while True:
            try:
                cmd_id, cmd = await conn.recv()
            except EOFError:
                logger.warning("Disconnected: %s" % conn)
                break
            Handler = commands.handlers[cmd['command']]
            handler = Handler(conn, self, cmd_id)
            try:
                envelope = {
                    "success": True,
                    "data": await handler.run(**cmd.get('args', {}))
                }
            except Exception as e:
                logger.exception('Command Exception')
                envelope = {
                    "success": False,
                    "exception": type(e).__name__,
                    "message": str(e)
                }
            await conn.send(cmd_id, envelope)

    def on_finish(self, task):
        conn = task.conn
        task.conn = None
        self.connections.remove(conn)
        try:
            task.result()
        except:
            logger.exception('Connection Exception')
        conn.close()
        logger.warning("Finished: %s" % conn)
