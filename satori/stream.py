from .frame import WindowUpdateFrame, HeadersFrame, FrameFlag, DataFrame, PushPromise
from .response import ClientResponse
import asyncio

import enum

MAX_STREAM_ID = (2 ** 31) - 1


# TODO(roasbeef): Change other Enums to IntEnums like this one.
class StreamState(enum.IntEnum):
    (IDLE, RESERVED_LOCAL, RESERVED_REMOTE, OPEN,
     HALF_CLOSED_REMOTE, HALF_CLOSED_LOCAL, CLOSED) = range(7)


# Need to handle some server push, pass in a response object to client handler,
# the handler has a push() method, write_header method (int arg means method
# response code).
# NEED TO STRONGLY CONSIDER MAKING THIS INTO TWO SUBCLASSES
class Stream(object):

    def __init__(self, stream_id, conn, encoder, decoder):
        self.stream_id = stream_id
        # Need to handle cases with push promises.
        self.state = StreamState.IDLE

        self._request_headers = {}
        self._response_headers = {}

        self._header_encoder = encoder
        self._header_decoder = decoder

        self._conn = conn

        self._frame_queue = asyncio.Queue()
        # A dictionary of Futures who's value will be the stream object
        # promised from this particular stream sometime in the future
        self._promised_streams = {}

        self._outgoing_flow_control = 65535
        self._incoming_flow_control = 65535

        # Start task to pop frames of queue, looking for a end

    def add_header(self, header_key, header_value, is_request_header):
        if is_request_header:
            self._request_headers[header_key.lower()] = header_value
        else:
            self._response_headers[header_key.lower()] = header_value

    def receive_promised_stream(stream):
        self._promised_streams[stream.stream_id].set_result(stream)

    def process_frame(self, frame):
        if isinstance(frame, WindowUpdateFrame):
            self._outgoing_flow_control += frame.window_size_increment
        else:
            self._frame_queue.put(frame)

    @asyncio.coroutine
    def _send_headers(self, end_headers, end_stream, is_request, priority=0):
        # How to handle outgoing data from stream?
        headers = HeadersFrame(self.stream_id, priority=priority)

        # Pending the API from Metehan.
        header_data = self._request_headers if is_request else self._response_headers
        headers.data = self._header_encoder.encode(header_data)

        if end_headers:
            headers.flags.add(FrameFlag.END_STREAM)
        if end_stream:
            headers.flags.add(FrameFlag.END_HEADERS)

        # Flow control?
        yield from self._conn.write_frame(headers)

    @asyncio.coroutine
    def _consume_raw_headers(self):
        raw_headers = bytearray()

        while True:
            # We should only be receiving headers frames at this point in the
            # stream's life cycle. Either the client is attempting to consume a
            # response, OR the server attempting to parse a request, and a
            # possibly subsequent body of that request, in the case of a POST
            # request.
            header_frame = yield from self._frame_queue.get()
            raw_headers.extend(header_frame.data)

            if FrameFlag.END_STREAM in header_frame.flags:
                self.state = StreamState.CLOSED

            if FrameFlag.END_HEADERS in header_frame.flags:
                break

        return raw_headers

    @asyncio.coroutine
    def _promise_push(self, headers):
        promise_frame = PushPromise(self.stream_id)
        promise_frame.promised_stream_id = self._conn.get_next_stream_id()
        promise_frame.data = self._header_decoder.encode(headers)

        self._promised_streams[promise_frame.promised_stream_id] = asyncio.Future()

        yield from self._conn.write_frame(promise_frame)

        return self._promised_streams[promise_frame.promised_stream_id]

    @asyncio.coroutine
    def _send_data(self, data, end_stream):
        # Need to handle padding also?
        # client case: post request
        # server case: sending back data for response
        data_frame = DataFrame(self.stream_id)
        data_frame.data = data
        if end_stream:
            data_frame.flags.add(FrameFlag.END_STREAM)

        yield from self._conn.write_frame(data_frame)

        # Transition stream state
        if end_stream:
            self.state = (StreamState.HALF_CLOSED_LOCAL if self.state == StreamState.OPEN
                          else StreamState.CLOSED)

    @asyncio.coroutine
    def _read_data(self, num_bytes):
        pass


    # Maybe should also create a BaseClass? But just override a few methods?
    @asyncio.coroutine
    def consume_request(self):
        encoded_headers = yield from self._consume_raw_headers()
        self.state = StreamState.OPEN
        self._request_headers = self._header_decoder.decode(encoded_headers)

        # For now, we'll only deal with POST and GET requests...
        if self._request_headers[':method'] not in ('POST', 'GET'):
            # Give 'em a 405
            self._response_headers[':status'] = 405
            # TODO(roasbeef): Is this the correct format for sending a header
            # with multiple values?
            self._response_headers['allow'] = "GET, POST"
            # TODO(roasbeef): Should I do away with the partition of headers?
            self._send_headers(end_headers=True, end_stream=True, is_request=False)

        # Possibly some request body.
        if self._request_headers[':method'] == 'POST':
            # TODO(roasbeef): Need to look at the content-type and handle accodingly
            post_data = yield from self._read_data()

        asyncio.async(self._conn.dispatch_response(self, req_body=post_data))

    @asyncio.coroutine
    def consume_response(self):
        # send window update frames for the stream_id once frames are popped
        # off.
        # First read until we have a end headers, then return a response object
        # that can continue to read off the connection.

        # At this point, state should be half closed local...

        # Wait till we have all the header block fragments and or continutation
        # frames
        raw_headers = yield from self._consume_raw_headers()
        self.state = StreamState.OPEN

        # Api subject to change
        response_headers = self._header_decoder.decode(raw_headers)
        # Return a response object here pass in headers and 'self'
        # Need to add a read method that the response uses?
        # if client, we'll return a response here
        return ClientResponse(response_headers, self)

    def close(self):
        pass

    @asyncio.coroutine
    def open_request(self, end_stream=False):
        # encode headers

        # create header frame

        # add the end headers flag to the header, unless it's over a certain
        # size, then we need to use some continuation frames.

        # send off the headers frame

        # state should be (half_closed_local) if end_stream otherwise shit is
        # open

        pass
