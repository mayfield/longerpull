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

    async def reply(self, message):
        """ Send a reply message using the msg_id of this command. """
        return await self.conn.send(self.msg_id, message)

    async def run(self, **command_args):
        raise NotImplementedError("Must be defined in subclass")


@export
class Authorize(CommandHandler):

    name = 'authorize'

    async def run(self, *, token_id=None, token_secret=None):
        await self.reply({"Hello": "World"})


@export
class Register(CommandHandler):

    name = 'register'

    async def run(self, *, product=None, mac=None, name=None):
        await self.reply({
            "client_id": 1,
            "token_id": 1,
            "token_secret": "abc"
        })


@export
class CheckActivation(CommandHandler):

    name = 'check_activation'

    async def run(self, *, secrethash=None):
        raise Exception("not supported")


@export
class Bind(CommandHandler):

    name = 'bind'

    async def run(self, *, client_id=None):
        self.server.register_rpc_handle(client_id)


@export
class StartPoll(CommandHandler):

    name = 'start_poll'

    async def run(self, *, args=None):
        self.conn.poll_id = self.msg_id
        #return {"response_queue": "return_addr", "response_id": 0, "request": {
        #    "system": "cs", "options": {}, "command": "get"}}


@export
class Post(CommandHandler):
    """ Message resulting from an event trigger placed on a client. """

    name = 'post'

    async def run(self, *, queue=None, id=None, value=None):
        logger.critical("post %s %s %s" % (queue, id, value))
