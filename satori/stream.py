from .frame import (WindowUpdateFrame, HeadersFrame, FrameFlag, DataFrame,
                    PushPromise, RstStreamFrame, PriorityFrame, DEFAULT_PRIORITY)
from .response import ClientResponse
import asyncio

import enum

MAX_STREAM_ID = (2 ** 31) - 1

import logging
logger = logging.getLogger('http2')
logger.setLevel(logging.INFO)


# TODO(roasbeef): Change other Enums to IntEnums like this one.
class StreamState(enum.IntEnum):
    (IDLE, RESERVED_LOCAL, RESERVED_REMOTE, OPEN,
     HALF_CLOSED_REMOTE, HALF_CLOSED_LOCAL, CLOSED) = range(7)


# NEED TO STRONGLY CONSIDER MAKING THIS INTO TWO SUBCLASSES
class Stream(object):

    def __init__(self, stream_id, conn, header_codec, priority=DEFAULT_PRIORITY):
        self.stream_id = stream_id
        self.state = StreamState.IDLE
        # Priority of a frame, lowest is the highest priority
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

        self._outgoing_window_update = asyncio.Event()


    def add_header(self, header_key, header_value, is_request_header):
        logging.info('Adding header to stream: %s' % self.stream_id)
        if is_request_header:
            self._request_headers[header_key.lower()] = header_value
        else:
            self._response_headers[header_key.lower()] = header_value

    def receive_promised_stream(self, stream):
        logger.info('got our promised stream')
        self._promised_streams[stream.stream_id].set_result(stream)

    def process_frame(self, frame):
        if isinstance(frame, WindowUpdateFrame):
            logger.info('GOT A WINDOW UPDATE FRAME FOR STREAM: %s, size increase: %s' % (frame.stream_id, frame.window_size_increment))
            print('Got a window update frame for stream: %s' % frame.stream_id)
            self._outgoing_flow_control_window += frame.window_size_increment
            # Notify the task sending data of an update, as it might be waiting
            # on one.
            logger.info('Letting task know that it can write stream')
            print('Letting task know that it can write stream')
            self._outgoing_window_update.set()
            self._outgoing_window_update.clear()
        # TODO(Roasbeef): Should we also update the priority of frames that
        # this stream has in the heapq?
        elif isinstance(frame, PriorityFrame):
            logger.info('Got a priority frame')
            self.priority = frame.priority
        elif isinstance(frame, RstStreamFrame):
            # Either a client has rejected a push promise
            # OR we just messed up somehow in regards to the defined stream
            # semantics.
            # Call self.close() ?
            pass
        else:
            logger.info('Frame sent to stream')
            logging.info('READ FRAME FROM SOCKET')
            logging.info('FrameType: %s' % frame.frame_type)
            logging.info('SteamId: %s' % frame.stream_id)
            logging.info('Length: %s' % frame.length)
            if isinstance(frame, DataFrame) or isinstance(frame, HeadersFrame):
                logging.info('Data: %s' % frame.data)
            self._frame_queue.put_nowait(frame)

    @asyncio.coroutine
    def _send_headers(self, end_headers, end_stream, priority=DEFAULT_PRIORITY):
        """ Method used by response objects on the server side. """
        logger.info('Sending headers to response')
        headers = HeadersFrame(self.stream_id, priority=priority)

        # Pending the API from Metehan.
        headers.data = self._header_codec.encode_headers(self._response_headers)

        if end_headers:
            logger.info('Last header to be sent for stream: %s' % self.stream_id)
            print('Last header to be sent for stream: %s' % self.stream_id)
            headers.flags.add(FrameFlag.END_HEADERS)
        if end_stream:
            logger.info('Last frame to be sent for stream: %s' % self.stream_id)
            print('Last frame to be sent for stream: %s' % self.stream_id)
            headers.flags.add(FrameFlag.END_STREAM)

        logger.info('Sending last frame')
        print('Sending last frame')
        # Flow control?
        yield from self._conn.write_frame(headers)

    @asyncio.coroutine
    def _consume_raw_headers(self):
        logger.info('Getting all the headers on stream: %s' % self.stream_id)
        raw_headers = bytearray()

        while True:
            # We should only be receiving headers frames at this point in the
            # stream's life cycle. Either the client is attempting to consume a
            # response, OR the server attempting to parse a request, and a
            # possibly subsequent body of that request, in the case of a POST
            # request.
            logger.info('Blocking to get headers on stream: %s' % self.stream_id)
            print('Blocking to get headers on stream: %s' % self.stream_id)
            header_frame = yield from self._frame_queue.get()
            logger.info('Stream got header frame: %s ' % self.stream_id)
            print('Stream got header frame: %s ' % self.stream_id)
            raw_headers.extend(header_frame.data)

            if FrameFlag.END_STREAM in header_frame.flags:
                logger.info('Last frame on stream: %s' % self.stream_id)
                print('Last frame on stream: %s' % self.stream_id)
                self.state = StreamState.CLOSED

            if FrameFlag.END_HEADERS in header_frame.flags:
                logger.info('No more headers to be gat, breaking: %s' % self.stream_id)
                print('No more headers to be gat, breaking: %s' % self.stream_id)
                break

        logger.info('Done getting all raw headers for stream: %s' % self.stream_id)
        print('Done getting all raw headers for stream: %s' % self.stream_id)
        return raw_headers

    @asyncio.coroutine
    def _promise_push(self, push_request_headers):
        logger.info('Trying to create new stream')
        promise_frame = PushPromise(self.stream_id)
        promise_frame.promised_stream_id = self._conn._get_next_stream_id()
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
        logger.info('Sending data on stream: %s' % self.stream_id)
        logger.info('Data: %s' % data)
        # Need to handle padding also?
        # client case: post request
        # server case: sending back data for response
        data_frame = DataFrame(self.stream_id)
        data_frame.data = data if type(data) is bytes else data.encode('ascii')
        if end_stream:
            logger.info('DONE SENDING DATA FOR STREAM: %s' % self.stream_id)
            data_frame.flags.add(FrameFlag.END_STREAM)

        # Do the 'wait till have room to write' dance here.
        while len(data_frame) > self._outgoing_flow_control_window:
            logger.info('waiting till we can send more data: %s' % stream_id)
            yield from self._outgoing_window_update.wait()
            logger.info('DONE waiting till we can send more data: %s' % stream_id)

        # TODO(roasbeef): Either chop up the frames here, or do it on the
        # PriorityQueueFrame level.
        logger.info('SENDING FRAME ON STREAM: %s' % self.stream_id)
        yield from self._conn.write_frame(data_frame)
        self._outgoing_flow_control_window -= len(data_frame)

        # Transition stream state
        if end_stream:
            self.state = (StreamState.HALF_CLOSED_LOCAL if self.state == StreamState.OPEN
                          else StreamState.CLOSED)

    @asyncio.coroutine
    def _read_data(self, num_bytes=None):
        logger.info('READING ALL THE DATA FOR STREAM: %s' % self.stream_id)
        frame_data = bytearray()

        # Return nothing if the stream is 'closed'
        if self.state == StreamState.CLOSED:
            return b''

        # TODO(roasbeef): Implement chunked reading via num_bytes
        # TODO(roasbeef): Regulate incoming flow control also.
        while num_bytes is None:
            logger.info('reading some data on stream: %s' % self.stream_id)
            frame = yield from self._frame_queue.get()
            frame_data.extend(frame.data)

            # assert isinstance(frame, DataFrame)

            # Last frame of the stream, we're done here.
            if FrameFlag.END_STREAM in frame.flags:
                self.state = (
                        StreamState.HALF_CLOSED_REMOTE if self.state == StreamState.OPEN
                        else StreamState.CLOSED
                )
                logger.info('last bit of data sent read on stream: %s' % self.stream_id)
                print('last bit of data sent read on stream: %s' % self.stream_id)
                break

            # Only send a flow control update if we actually received data.
            if len(frame):
                print('READ OF A FRAME, SENDING THE FLOW CONTROL UPDATE FOR IT: %s' % self.stream_id)
                yield from self._conn.update_incoming_flow_control(increment=len(frame),
                                                                   stream_id=self.stream_id)


        logger.info('data read: %s' % frame_data)
        return frame_data


    # Maybe should also create a BaseClass? But just override a few methods?
    @asyncio.coroutine
    def consume_request(self):
        logger.info('SERVER CONSUMING REQUEST, STREAM ID: %s' % self.stream_id)
        encoded_headers = yield from self._consume_raw_headers()
        self.state = StreamState.OPEN
        self._request_headers = self._header_codec.decode_headers(encoded_headers)
        logger.info('Got these headers: %s, on stream %s' % (self._request_headers, self.stream_id))

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
        else:
            post_data = None

        logger.info('Dispatching response for stream, %s' % self.stream_id)
        yield from self._conn.dispatch_response(request_stream=self, req_body=post_data)

    @asyncio.coroutine
    def consume_response(self):
        # Wait till we have all the header block fragments and or continutation
        # frames
        logger.info('Client is consuming responsef for stream, %s' % self.stream_id)
        raw_headers = yield from self._consume_raw_headers()
        self.state = StreamState.OPEN

        response_headers = self._header_codec.decode_headers(raw_headers)
        logger.info('Got these headers: %s , for stream %s' % (response_headers, self.stream_id))

        # Since we have the headers, we can return a response to the client,
        # the body of the response might still be on the way.
        return ClientResponse(response_headers, self)

    def close(self):
        pass

    @asyncio.coroutine
    def open_request(self, body=None, end_stream=True):
        encoded_request_headers = self._header_codec.encode_headers(self._request_headers)
        logger.info('Sending headers for request, and stream: %s %s' % (self._request_headers, self.stream_id))

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
        logger.info('Sending headers frame for stream: %s' % self.stream_id)
        yield from self._conn.write_frame(headers)

        # Possibly send over a POST body.
        if body is not None:
            self._send_data(body, end_stream)


        # If we're done sending data, then close off the stream locally.
        self.state = StreamState.HALF_CLOSED_LOCAL if end_stream else StreamState.OPEN
