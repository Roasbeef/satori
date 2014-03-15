from .protocol import HTTP2CommonProtocol, HANDSHAKE_CODE
from .response import ServerResponse
import asyncio
import collections

class HTTP2Server(HTTP2CommonProtocol):
    def __init__(self, server_settings):
        super().__init__(is_client=False)
        self._server_settings = server_settings
        self._routes = {}

    def async_route(self, route, **options):
        def decorator(f):
            self._routes[route] = asyncio.coroutine(f)
            return f
        return decorator


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
        requested_route = request_stream._request_headers[':path']
        if request_route in self._routes:
            handler_func = self._routes[request_stream]
            server_response = ServerResponse({}, request_stream)
            yield from handler_func(request_stream._request_headers,
                                    server_response, {})

def create_server(http2_settings, port, host=None, *,
                  klass=HTTP2Server, **kwargs):
    return (yield from asyncio.get_event_loop().create_server(
        lambda: klass(http2_settings), host, port, **kwargs)
    )
