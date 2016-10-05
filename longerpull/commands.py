"""
LP commands
"""

import collections
import itertools
import json
import logging
import struct
import zlib

logger = logging.getLogger('longerpull')
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
async def authorize_command(username=None, password=None):
    pass


@command
async def check_activation():
    pass
