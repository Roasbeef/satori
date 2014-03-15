from .protocol import HTTP2CommonProtocol
import asyncio
import collections

class HTTP2Server(HTTP2CommonProtocol):
    def __init__(self):
        super().__init__(is_client=False)
        self._routes = {}

    def connection_made(self, transport):
        super().connection_made(transport)
        yield from settings_handshake()

    @asyncio.coroutine
    def settings_handshake(self):
        pass

    @asyncio.coroutine
    def dispatch_response(request_stream, req_body=None):
        # Look the the request headers of the stream, find the proper coroutine
        # handler from the map. `yield from` it, letting it handle the request
        # and do w/e else it needs to.
        pass


def create_server():
    pass
