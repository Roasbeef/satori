from .protocol import HTTP2CommonProtocol, HANDSHAKE_CODE
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
        handshake_bytes = yield from self.reader.read(24)
        if handshake_bytes == HANDSHAKE_CODE:
            header_bytes = yield from self.reader.read(8)
            frame_header = FrameHeader.from_raw_bytes(header_bytes)
            
            payload_bytes = yield from self.reader.read(frame_header.length)
            frame = Frame.from_frame_header(frame_header)
            
            frame.deserialize(payload_bytes)
            self.update_settings(frame)
            
            our_settings = SettingsFrame(stream_id=0, settings=self._server_settings)
            self.writer.write(our_settings.serialize())

            # Off to the races.
            self._connection_header_exchanged.set_result(True)
        else:
            pass
    @asyncio.coroutine
    def dispatch_response(request_stream, req_body=None):
        # Look the the request headers of the stream, find the proper coroutine
        # handler from the map. `yield from` it, letting it handle the request
        # and do w/e else it needs to.
        pass


def create_server():

    
