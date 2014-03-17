from .protocol import HTTP2CommonProtocol, HANDSHAKE_CODE
from .response import ServerResponse
from .frame import HeadersFrame, SettingsFrame, FrameHeader, Frame
import asyncio
import collections
import sys

import logging
logger = logging.getLogger('http2')
logger.setLevel(logging.INFO)
if not logger.handlers:
    out_hdlr = logging.StreamHandler(sys.stdout)
    out_hdlr.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(lineno)d - %(module)s - %(funcName)s - %(message)s'))
    out_hdlr.setLevel(logging.INFO)
    logger.addHandler(out_hdlr)

class HTTP2Server(HTTP2CommonProtocol):
    def __init__(self, route_handler, server_settings):
        self._server_settings = server_settings
        self._handler = route_handler
        self._routes = {}
        super().__init__(is_client=False)


    def connection_made(self, transport):
        logging.info('Connection made for sever')
        super().connection_made(transport)
        logging.info('Waiting for handhskae')
        asyncio.async(self.settings_handshake())

    @asyncio.coroutine
    def settings_handshake(self):
        logging.info('Trying to read handshake bytes')
        handshake_bytes = yield from self.reader.read(24)
        if handshake_bytes == HANDSHAKE_CODE:
            logging.info('Server got the client connection header')
            header_bytes = yield from self.reader.read(8)
            frame_header = FrameHeader.from_raw_bytes(header_bytes)

            payload_bytes = yield from self.reader.read(frame_header.length)
            frame = Frame.from_frame_header(frame_header)

            frame.deserialize(payload_bytes)
            logging.info('Server got initial settings frame.')
            self.update_settings(frame)

            logging.info('Server sending its settings frame.')
            our_settings = SettingsFrame(stream_id=0, settings=self._server_settings)
            self.writer.write(our_settings.serialize())

            # Off to the races.
            logging.info('Server handshake done.')
            self._connection_header_exchanged.set_result(True)
        else:
            logging.info('Client handshake invalid.')
            yield from self.close_connection()

    @asyncio.coroutine
    def dispatch_response(self, request_stream, req_body=None):
        # Look the the request headers of the stream, find the proper coroutine
        # handler from the map. `yield from` it, letting it handle the request
        # and do w/e else it needs to.
        requested_route = request_stream._request_headers[':path']
        server_response = ServerResponse({}, request_stream)
        logger.info('Processing request')
        yield from self._handler(request_stream._request_headers,
                                 server_response, {})
        logger.info('Done with request')

@asyncio.coroutine
def serve(route_handler, http2_settings, port, host=None, *,
          klass=HTTP2Server, **kwargs):
    return (yield from asyncio.get_event_loop().create_server(
        lambda: klass(route_handler, http2_settings), host, port, **kwargs)
    )
