"""
Longer Pull Server
"""

import aiocluster
import functools
import logging
from . import protocol, commands

logger = logging.getLogger('lp.server')


@functools.lru_cache(maxsize=4096)
def get_handler(cmd, conn, server, cmd_id):
    """ Cache command instances for performance. """
    return commands.handlers[cmd](conn, server, cmd_id)


class LPServer(aiocluster.WorkerService):

    def __init__(self, *args, **kwargs):
        self.connections = set()
        super().__init__(*args, **kwargs)

    async def run(self, addr='0.0.0.0', port=8001):
        server = await self._loop.create_server(self.protocol_factory, addr,
                                                port, reuse_port=True,
                                                backlog=15000)
        await server.wait_closed()

    def protocol_factory(self):
        connect_waiter = self._loop.create_future()
        c = protocol.LPConnection(connect_waiter, loop=self._loop)
        connect_waiter.add_done_callback(self.on_connect)
        return c.protocol

    def on_connect(self, f):
        conn = f.result()
        self._loop.create_task(self.monitor_connection(conn))

    async def monitor_connection(self, conn, _nokwargs={}):
        cmd_handlers = commands.handlers
        self.connections.add(conn)
        try:
            while True:
                cmd_id, cmd = await conn.recv_message()
                handler = cmd_handlers[cmd['command']](conn, self, cmd_id)
                kwargs = cmd['args'] if 'args' in cmd else _nokwargs
                await handler.run(**kwargs)
        except (protocol.ConnectionLost, ConnectionError):
            pass
        except Exception:
            logger.exception('Connection Exception')
        finally:
            # XXX
            #logger.warning("Closing: %s" % conn)
            self.connections.remove(conn)
            conn.close()
            #print("XXX: checking for cycles ")
            assert conn.protocol._conn is None
