from .protocol import HTTP2CommonProtocol
import asyncio
import collections

class HTTP2ClientConnection(HTTP2CommonProtocol):
    def __init__(self):
        super().__init__(is_client=True)

    @asyncio.coroutine
    def request(self, method, resource, body=None, headers={}):
        stream = self._new_stream()
        stream.add_header(':method', method.upper(), is_request_header=True)
        stream.add_header(':path', resource, is_request_header=True)
        stream.add_header(':scheme', 'http', is_request_header=True)  # TODO(roasbeef): Need to add HTTPS support
        stream.add_header(':authority', self._host, is_request_header=True)

        for header_key, header_val in headers.items():
            stream.add_header(header_key, header_val, is_request_header=True)

        if isinstance(body, str):
            body = body.encode('utf-8')

        # Officially 'open' the stream, by sendin over our HEADERS.
        yield from stream.open_request(body=body, end_stream=True)

        return (yield from self.stream.consume_response())


    @asyncio.coroutine
    def settings_handshake(self, host):
        self._host = host
        pass

def connect(uri, options={}, *, klass=HTTP2ClientConnection, **kwargs):
    host, post = uri.split(':')
    transport, protocol = asyncio.get_event_loop().create_connection(
            klass, host, port, **kwargs)

    try:
        yield from protocol.settings_handshake(host)
    except: # What to do here?
        pass

    return protocol
