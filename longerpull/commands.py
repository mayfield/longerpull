"""
LP commands
"""

import functools
import logging

logger = logging.getLogger('lp.commands')
commands = {}


def require_auth(func):
    """ Decorator to require valid auth on a connection before allowing use
    of a command. """

    @functools.wraps(func)
    def wrap(*args, **kwargs):
        logger.warning("REQUIRE AUTH NOT IMPLEMENTED")
        return func(*args, **kwargs)
    return wrap


def command(func):
    """ Decorator to register a function as a viable lp command. """
    logger.info("Registering command: %s" % func.__name__)
    commands[func.__name__] = func
    return func


@command
async def authorize(username=None, password=None,
                    token_id=None, token_secret=None):
    return {"Hello": "World"}


@command
async def register(product=None, mac=None, name=None):
    return {"client_id": 1, "token_id": 1, "token_secret": "abc"}


@command
async def check_activation(secrethash=None):
    raise Exception("not supported")


@command
async def bind(client_id=None):
    return True

@command
async def start_poll(args=None):
    return {"response_queue": "return_addr", "response_id": 0, "request": {
        "system": "cs", "options": {}, "command": "get"}}
