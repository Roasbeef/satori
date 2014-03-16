from .frame import DEFAULT_PRIORITY
import asyncio
import json

import logging
logger = logging.getLogger('http2')
logger.setLevel(logging.INFO)


class BaseResponse(object):
    def __init__(self, headers, stream):
        self.headers = headers
        self._stream = stream

        self._cookies = {}

    def __bool__(self):
        return 200 <= self.status_code <= 300


class ClientResponse(BaseResponse):
    def __init__(self, headers, stream):
        super().__init__(headers, stream)
        self.body = None

    @asyncio.coroutine
    def read_body(self):
        logging.info('Reading stream data')
        self.body = yield from self._stream._read_data()
        logging.info('Done reading stream data')
        return self.body

    @property
    def status_code(self):
        return int(self.headers[':status'])


    @property
    def json(self):
        if self._headers['Content-Type'] == 'application/json':
            return json.loads(self.body)


class ServerResponse(BaseResponse):
    def __init__(self, headers, stream):
        super().__init__(headers, stream)
        self._push_promises = {}

    # TODO(roasbeef): Support trailing headers?
    @asyncio.coroutine
    def end_headers(self, priority=DEFAULT_PRIORITY):
        # Send off the headers frame(s) via this stream.
        logging.info('Server sending over response headers')
        self._stream._response_headers = self.headers
        yield from self._stream._send_headers(end_headers=True, end_stream=False,
                                              priority=priority)

    @asyncio.coroutine
    def write(self, data, end_stream):
        logging.info('Server writing data to stream')
        if end_stream:
            logging.info('SERVER DONE SENDING DATA')
        yield from self._stream._send_data(data, end_stream)

    @asyncio.coroutine
    def write_static_file(self, file_path):
        pass

    @asyncio.coroutine
    def init_push(self, push_request_headers):  # TODO(roasbeef): Also allow push response headers here?
        logging.info('Server is trying to push a promise')
        # Create a new push promise, sending over the headers.
        # The initial headers need to be as if the server is sending the
        # headers pertaining to an original request for that resource.
        push_request_headers[':method'] = 'GET'
        promised_stream = yield from self._stream._promise_push(push_request_headers)

        promised_stream.add_header(':status', '200', is_request_header=False)
        yield from promised_stream._send_headers(end_headers=True, end_stream=False)
        #promised_stream.state = StreamState.HALF_CLOSED_LOCAL

        # create new response, wrap in stream
        # need to pass in headers here? shouldn't be blank?
        # Create a diff PushResponse class?
        push_response = ServerResponse({}, promised_stream)

        # send over the (push promise) headers frame
        # some future that's set if we get a rst stream?

        # return the response that has this new stream wrapped in it
        return push_response
