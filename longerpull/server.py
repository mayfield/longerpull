"""
Longer Pull Server
"""

import aiocluster
import asyncio
import functools
import logging
import socket
from . import connection, commands

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
        server = await asyncio.start_server(self.on_connect, addr, port,
                                            reuse_port=True, backlog=1000,
                                            loop=self._loop)
        await server.wait_closed()

    def on_connect(self, reader, writer):
        """ Handle new LP connection. """
        self.adj_socket(writer.get_extra_info('socket'))
        conn = connection.LPServerConnection(reader, writer)
        self.connections.add(conn)
        t = self._loop.create_task(self.monitor_connection(conn))
        t.conn = conn
        t.add_done_callback(self.on_finish)

    def adj_socket(self, sock):
        """ Disable Nagle algo, etc. """
        assert not sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    async def monitor_connection(self, conn):
        logger.info("Connected: %s" % conn)
        try:
            await conn.check_version()
        except connection.BadVersion as e:
            logger.warning(e)
            return
        nokwargs = {}
        cmd_handlers = commands.handlers
        while True:
            cmd_id, cmd = await conn.recv()
            handler = cmd_handlers[cmd['command']](conn, self, cmd_id)
            kwargs = cmd['args'] if 'args' in cmd else nokwargs
            try:
                await handler.run(**kwargs)
            except Exception as e:
                logger.exception('Command Exception: %s' % handler.name)
                break

    def on_finish(self, task):
        conn = task.conn
        task.conn = None
        self.connections.remove(conn)
        conn.close()
        try:
            task.result()
        except (ConnectionResetError, EOFError):
            pass
        except OSError as exc:
            logger.exception('XXX You should probably be handling this.  Check it out')
            import pdb
            pdb.set_trace()
        except Exception:
            logger.exception('Connection Exception')
        finally:
            logger.warning("Finished: %s" % conn)
