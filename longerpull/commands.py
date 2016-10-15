"""
LP commands
"""

import functools
import logging

logger = logging.getLogger('lp.commands')
handlers = {}


def require_auth(func):
    """ Decorator to require valid auth on a connection before allowing use
    of a command. """

    @functools.wraps(func)
    def wrap(*args, **kwargs):
        logger.warning("REQUIRE AUTH NOT IMPLEMENTED")
        return func(*args, **kwargs)
    return wrap


def export(cls):
    handlers[cls.name] = cls
    return cls


class CommandHandler(object):

    __slots__ = (
        'conn',
        'server',
        'msg_id',
    )

    name = None

    def __init__(self, conn, server, msg_id):
        self.conn = conn
        self.server = server
        self.msg_id = msg_id

    def reply(self, message):
        """ Send a successful reply message. """
        self.conn.send(self.msg_id, {
            "success": True,
            "data": message
        })

    def reply_exception(self, exc, name=None, msg=None, extra={}):
        """ Exceptional reply to a command. """
        if name is None:
            name = type(exc).__name__.lower()
        if msg is None:
            msg = str(exc)
        resp = {
            "success": False,
            "exception": name,
            "message": msg,
        }
        resp.update(extra)
        self.conn.send(self.msg_id, resp)

    async def run(self, **command_args):
        raise NotImplementedError("Must be defined in subclass")


@export
class Authorize(CommandHandler):

    name = 'authorize'

    async def run(self, *, username=None, password=None, token_id=None,
                  token_secret=None):
        self.reply({"Hello": "World"})


@export
class Register(CommandHandler):

    name = 'register'

    async def run(self, *, product=None, mac=None, name=None):
        self.reply({
            "client_id": 1,
            "token_id": 1,
            "token_secret": "abc"
        })


@export
class CheckActivation(CommandHandler):

    name = 'check_activation'

    async def run(self, *, secrethash=None):
        self.reply_exception(NotImplementedError(), name='notregistered')


@export
class Bind(CommandHandler):

    name = 'bind'

    async def run(self, *, client_id=None):
        #self.server.register_rpc_handle(client_id)
        # XXX: HMMMM
        self.reply(None)  # Ack


@export
class StartPoll(CommandHandler):

    name = 'start_poll'

    async def run(self, *, args=None):
        self.conn.poll_id = self.msg_id
        self.reply({
            "response_queue": "return_addr",
            "response_id": 0,
            "request": {
                "system": "cs",
                "command": "get",
                "options": {
                    "path": "status.product_info.mac0"
                },
                "event_trigger": {
                    "system": "cs",
                    "id": 0,
                    "trigger": {
                        "event": 'put',
                        "path": 'config',
                        "delay": 0
                    }
                }
            }
        })

import time
last = start = time.perf_counter()
import itertools
counter = itertools.count()
last_c = 0

@export
class Post(CommandHandler):
    """ Message resulting from an event trigger placed on a client. """

    name = 'post'

    async def run(self, *, queue=None, id=None, value=None):
        c = next(counter)
        self.reply(None)
        now = time.perf_counter()
        if now - last > 5:
            global last_c, last
            print("%d msg/s" % round((c - last_c) / (now - last)))
            last_c = c
            last = now
        #logger.critical("post %s %s %s" % (queue, id, value))
