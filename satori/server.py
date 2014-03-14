from .protocol import HTTP2CommonProtocol
import asyncio
import collections

class HTTP2Server(HTTP2CommonProtocol):
    def __init__(self):
        super().__init__(is_client=False)

    def connection_made(self, transport):
        super().connection_made(transport)
        yield from settings_handshake()

    @asyncio.coroutine
    def settings_handshake(self):
        pass


def create_server():
    pass
