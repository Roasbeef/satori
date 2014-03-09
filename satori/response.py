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
        pass

    @property
    def status_code(self):
        return int(self._headers[':status'])


class ServerResponse(BaseResponse):
    def __init__(self, headers, stream):
        super().__init__(headers, stream)

    @asyncio.coroutine
    def end_headers(self):
        # send off the headers frame(s) via this stream
        pass

    @asyncio.coroutine
    def write(self):
        pass
