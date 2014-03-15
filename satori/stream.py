from .frame import (WindowUpdateFrame, HeadersFrame, FrameFlag, DataFrame,
                    PushPromise, RstStreamFrame, PriorityFrame)
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

    def __init__(self, stream_id, conn, header_codec):
    def __init__(self, stream_id, conn, header_codec, priority=0):
        self.stream_id = stream_id
        # Need to handle cases with push promises.
        self.state = StreamState.IDLE
        self.priority = priority

        self._request_headers = {}
        self._response_headers = {}

        self._header_codec = header_codec

        self._conn = conn

        self._frame_queue = asyncio.Queue()
        # A dictionary of Futures who's value will be the stream object
        # promised from this particular stream sometime in the future
        self._promised_streams = {}

        self._outgoing_flow_control_window = 65535
        self._incoming_flow_control_window = 65535

        self._outgoing_window_update = asyncio.Event()


    def add_header(self, header_key, header_value, is_request_header):
        if is_request_header:
            self._request_headers[header_key.lower()] = header_value
        else:
            self._response_headers[header_key.lower()] = header_value

    def receive_promised_stream(self, stream):
        self._promised_streams[stream.stream_id].set_result(stream)

    def process_frame(self, frame):
        if isinstance(frame, WindowUpdateFrame):
            self._outgoing_flow_control_window += frame.window_size_increment
            # Notify the task sending data of an update, as it might be waiting
            # on one.
            self._outgoing_window_update.set()
            self._outgoing_window_update.clear()
        # TODO(Roasbeef): Should we also update the priority of frames that
        # this stream has in the heapq?
        elif isinstance(frame, PriorityFrame):
            self.priority = frame.priority
        elif isinstance(frame, RstStreamFrame):
            # Either a client has rejected a push promise
            # OR we just messed up somehow in regards to the defined stream
            # semantics.
            # Call self._close() ?
            # Call self.close() ?
            pass
        else:
            self._frame_queue.put(frame)

    @asyncio.coroutine
    def _send_headers(self, end_headers, end_stream, priority=0):
        """ Method used by response objects on the server side. """
        headers = HeadersFrame(self.stream_id, priority=priority)

        # Pending the API from Metehan.
        headers.data = self._header_codec.encode_headers(self._response_headers)

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
    def _promise_push(self, push_request_headers):
        promise_frame = PushPromise(self.stream_id)
        promise_frame.promised_stream_id = self._conn.get_next_stream_id()
        promise_frame.data = self._header_codec.encode_headers(push_request_headers)

        # Create a new future to keep track of when the stream is 'ready' for
        # writing by the callee.
        self._promised_streams[promise_frame.promised_stream_id] = asyncio.Future()

        yield from self._conn.write_frame(promise_frame)

        # Return the newly created stream.
        yield from self._promised_streams[promise_frame.promised_stream_id]
        return self._promised_streams[promise_frame.promised_stream_id].result()

    # Call this using a task? In order for the window update wait to work?
    @asyncio.coroutine
    def _send_data(self, data, end_stream):
        # Need to handle padding also?
        # client case: post request
        # server case: sending back data for response
        data_frame = DataFrame(self.stream_id)
        data_frame.data = data
        if end_stream:
            data_frame.flags.add(FrameFlag.END_STREAM)

        # Do the 'wait till have room to write' dance here.
        while len(data_frame) > self._outgoing_flow_control_window:
            yield from self._outgoing_window_update.wait()

        # TODO(roasbeef): Either chop up the frames here, or do it on the
        # PriorityQueueFrame level.
        yield from self._conn.write_frame(data_frame)
        self._outgoing_flow_control_window -= len(data_frame)

        # Transition stream state
        if end_stream:
            self.state = (StreamState.HALF_CLOSED_LOCAL if self.state == StreamState.OPEN
                          else StreamState.CLOSED)

    @asyncio.coroutine
    def _read_data(self, num_bytes=None):
        frame_data = bytearray()

        # Return nothing if the stream is 'closed'
        if self.state = StreamState.CLOSED:
            return b''

        # TODO(roasbeef): Implement chunked reading via num_bytes
        # TODO(roasbeef): Regulate incoming flow control also.
        while num_bytes is None:
            data = yield from self._frame_queue.get()
            frame_data.extend(data)

            # Last frame of the stream, we're done here.
            if FrameFlag.END_STREAM in frame.flags:
                self.state = (
                        StreamState.HALF_CLOSED_REMOTE if self.state == StreamState.OPEN
                        else StreamState.CLOSED
                )
                break

            # Only send a flow control update if we actually received data.
            if len(frame):
                yield from self._conn.update_incoming_flow_control(increment=len(frame),
                                                                   stream_id=self.stream_id)

        return frame_data


    # Maybe should also create a BaseClass? But just override a few methods?
    @asyncio.coroutine
    def consume_request(self):
        encoded_headers = yield from self._consume_raw_headers()
        self.state = StreamState.OPEN
        self._request_headers = self._header_codec.decode_headers(encoded_headers)

        # For now, we'll only deal with POST and GET requests...
        if self._request_headers[':method'] not in ('POST', 'GET'):
            # Give 'em a 405
            self._response_headers[':status'] = 405
            # TODO(roasbeef): Is this the correct format for sending a header
            # with multiple values?
            self._response_headers['allow'] = "GET, POST"
            # TODO(roasbeef): Should I do away with the partition of headers?
            self._send_headers(end_headers=True, end_stream=True, is_request=False)

            self.state = StreamState.CLOSED
            return

        # Possibly some request body.
        if self._request_headers[':method'] == 'POST':
            # TODO(roasbeef): Need to look at the content-type and handle accodingly
            post_data = yield from self._read_data()

        asyncio.async(self._conn.dispatch_response(self, req_body=post_data))

    @asyncio.coroutine
    def consume_response(self):
        # Wait till we have all the header block fragments and or continutation
        # frames
        raw_headers = yield from self._consume_raw_headers()
        self.state = StreamState.OPEN

        response_headers = self._header_codec.decode_headers(raw_headers)

        # Since we have the headers, we can return a response to the client,
        # the body of the response might still be on the way.
        return ClientResponse(response_headers, self)

    def close(self):
        pass

    @asyncio.coroutine
    def open_request(self, body=None, end_stream=True):
        encoded_request_headers = self._header_codec.encode_headers(self._request_headers)

        # TODO(roasbeef): Need to handle chunked sending of headers via
        # CONTINUTATION frames.
        headers = HeadersFrame(self.stream_id)
        headers.data = encoded_request_headers

        # Since we're not supporting CONTINUATION frames for now, signal the
        # end of HEADERS on this stream.
        headers.flags.add(FrameFlag.END_HEADERS)

        if end_stream and body is None:
            headers.flags.add(FrameFlag.END_STREAM)

        # Send off the headers frame
        yield from self._conn.write_frame(headers)

        # Possibly send over a POST body.
        if body is not None:
            self._send_data(body, end_stream)


        # If we're done sending data, then close off the stream locally.
        self.state = StreamState.HALF_CLOSED_LOCAL if end_stream else StreamState.OPEN
