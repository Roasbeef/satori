from .protocol import HTTP2CommonProtocol
import asyncio
import collections

class HTTP2Server(HTTP2CommonProtocol):
    def __init__(self):
        self.upcoming_stream_id = 0

    def handshake(self):
        pass

