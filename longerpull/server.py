"""
Longer Pull Server
"""

import asyncio
import logging
import shellish
from . import protocol, commands

logger = logging.getLogger('lp.server')


class LPServer(shellish.Command):

    name = 'lpserver'

    def __init__(self, *args, **kwargs):
        self.connections = set()
        self.conn_pause_count = 0
        self.conn_recv_enqueue = 0
        self.conn_recv_dequeue = 0
        self.conn_recv_wait = 0
        self.conn_recv_direct = 0
        super().__init__(*args, **kwargs)

    def setup_args(self, parser):
        self.add_argument("--addr", default='0.0.0.0')
        self.add_argument("--port", default=8001, type=int)

    async def run(self, args):
        addr = args.addr
        port = args.port
        lpserver = await self._loop.create_server(self.protocol_factory, addr,
                                                  port, reuse_port=True)
        self._loop.create_task(self.xxx_debug_stuff())
        await lpserver.wait_closed()

    async def xxx_debug_stuff(self):
        import psutil
        ps = psutil.Process()
        while True:
            msg_buffers = 0
            msg_buffer_sz_est = 0
            pbuf = 0
            paused = 0
            for x in self.connections:
                if x.protocol._buffer:
                    pbufsize = len(x.protocol._buffer)
                else:
                    pbufsize = 0
                msg_buffers += len(x._recv_queue) if x._recv_queue else 0
                pbuf += pbufsize
                paused += int(x._paused)
            conn_count = len(self.connections)
            if conn_count:
                mem = ps.memory_info().rss
                per_conn_est = 26700 * conn_count
                mem_est = per_conn_est + msg_buffer_sz_est
                print()
                #print("ev scheduled:     ", len(self._loop._scheduled))
                #print("ev ready:         ", len(self._loop._ready))
                print("recv direct:      ", self.conn_recv_direct)
                print("recv enqueue:     ", self.conn_recv_enqueue)
                print("recv dequeue:     ", self.conn_recv_dequeue)
                print("recv wait:        ", self.conn_recv_wait)
                print("conns:            ", conn_count)
                print("paused conns:     ", paused)
                print("paused count:     ", self.conn_pause_count)
                print("mem:              ", mem, mem / conn_count)
                print("mem est:          ", mem_est, mem / mem_est)
                print("msg_buffers:      ", msg_buffers, msg_buffers / conn_count)
                print("protocol buffer:  ", pbuf, pbuf / conn_count)
            await asyncio.sleep(10)

    def protocol_factory(self):
        connect_waiter = self._loop.create_future()
        c = protocol.LPConnection(connect_waiter, server=self,
                                  loop=self._loop)
        connect_waiter.add_done_callback(self.on_connect)
        return c.protocol

    def on_connect(self, f):
        conn = f.result()
        self._loop.create_task(self.monitor_connection(conn))

    async def monitor_connection(self, conn, _nokwargs={}):
        logger.info('Established: %s' % conn)
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
            logger.warning("Closing: %s" % conn)
            self.connections.remove(conn)
            conn.close()
