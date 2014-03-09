from .protocol import HTTP2CommonProtocol
import asyncio
import collections

class HTTP2ClientConnection(HTTP2CommonProtocol):
    def __init__(self):
        self.upcoming_stream_id = 1

    def open_connection(self):
        pass

    def handshake(self):
        pass
