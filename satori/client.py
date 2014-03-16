from .protocol import HTTP2CommonProtocol, HANDSHAKE_CODE
from .frame import SettingsFrame, DataFrame, FrameHeader
import asyncio
import collections

import logging
import sys

logger = logging.getLogger('http2')
logger.setLevel(logging.INFO)

class HTTP2ClientConnection(HTTP2CommonProtocol):
    def __init__(self, client_settings):
        logger.info('In client constructor')
        super().__init__(is_client=True)
        self._client_settings = client_settings
        logger.info('Leaving client constructor')

    @asyncio.coroutine
    def request(self, method, resource, body=None, headers={}):
        logger.info('Creating request stream.')
        stream = self._new_stream()
        stream.add_header(':method', method.upper(), is_request_header=True)
        stream.add_header(':path', resource, is_request_header=True)
        stream.add_header(':scheme', 'http', is_request_header=True)  # TODO(roasbeef): Need to add HTTPS support
        stream.add_header(':authority', self._host, is_request_header=True)

        for header_key, header_val in headers.items():
            stream.add_header(header_key, header_val, is_request_header=True)

        if isinstance(body, str):
            body = body.encode('utf-8')

        logger.info('Opening request stream: %s' % stream.stream_id)
        # Officially 'open' the stream, by sendin over our HEADERS.
        yield from stream.open_request(body=body, end_stream=True)

        logger.info('Waiting for the response stream: %s' % stream.stream_id)
        return (yield from self.stream.consume_response())


    @asyncio.coroutine
    def settings_handshake(self, host):
        logger.info('Creating our settings handshake')
        our_settings = SettingsFrame(stream_id=0, settings=self._client_settings)

        logger.info('Client sending handshake')
        self.writer.write(HANDSHAKE_CODE)
        logger.info('Client sending settings frame')
        self.writer.write(our_settings.serialize())

        logger.info('Getting the server settings frame header')
        header_bytes = yield from self.reader.read(8)
        frame_header = FrameHeader.from_raw_bytes(header_bytes)

        logger.info('Getting the payload from the server')
        payload_bytes = yield from self.reader.read(frame_header.length)
        frame = Frame.from_frame_header(frame_header)

        frame.deserialize(payload_bytes)
        logger.info('Updating our settings')
        self.update_settings(frame)
        logger.info('CLIENT HANDSHAKE DONE')
        self._connection_header_exhanged.set_result(True)



@asyncio.coroutine
def connect(uri, options={}, *, klass=HTTP2ClientConnection, **kwargs):
    logger.info('Connecting to server')
    host, port = uri.split(':')
    transport, protocol = yield from asyncio.get_event_loop().create_connection(
            lambda: klass(options), host, port, **kwargs)

    logger.info('Created protocol')

    try:
        logger.info('Trying the handshake')
        yield from protocol.settings_handshake(host)
        logger.info('Handshake dunzo')
    except Exception as e: # What to do here?
        logger.info('Exception was thrown while trying the handshake.')
        raise e
        sys.exit(1)


    logger.info('Passing main connection to client')
    return protocol
