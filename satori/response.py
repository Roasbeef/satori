import asyncio


class BaseResponse(object):
    def __init__(self, headers, stream):
        self._headers = headers
        self._stream = stream

        self._cookies = {}

    def __bool__(self):
        return 200 <= self.status_code <= 300


class ClientResponse(BaseResponse):
    def __init__(self, headers, stream):
        super().__init__(headers, stream)

    @asyncio.coroutine
    def read_body(self):
        # will yield from the _read method of the stream
        pass

    @property
    def status_code(self):
        return int(self._headers[':status'])

    @property
    def json(self):
        pass


class ServerResponse(BaseResponse):
    def __init__(self, headers, stream):
        super().__init__(headers, stream)
        self._push_promises = {}

    # TODO(roasbeef): Support trailing headers?
    @asyncio.coroutine
    def end_headers(self):
        # send off the headers frame(s) via this stream
        # yield from self._stream.send_headers(self._header
        pass

    @asyncio.coroutine
    def write(self, data):
        pass

    @asyncio.coroutine
    def write_file(self, file_path):
        pass

    @asyncio.coroutine
    def init_push(self, headers):
        # Create a new push promise, sending over the headers.
        promised_stream = yield from self._stream._promise_push(headers)
        # create new response, wrap in stream
        # need to pass in headers here? shouldn't be blank?
        # Create a diff PushResponse class?
        push_response = ServerResponse(headers, promised_stream)

        # send over the (push promise) headers frame
        # some future that's set if we get a rst stream?

        # return the response that has this new stream wrapped in it
        return push_response
        pass
