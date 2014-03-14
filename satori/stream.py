from .frame import WindowUpdateFrame
import asyncio

import enum


# TODO(roasbeef): Change other Enums to IntEnums like this one.
class StreamState(enum.IntEnum):
    (IDLE, RESERVED_LOCAL, RESERVED_REMOTE, OPEN,
     HALF_CLOSED_REMOTE, HALF_CLOSE_LOCAL, CLOSED) = range(7)


# Need to handle some server push, pass in a response object to client handler,
# the handler has a push() method, write_header method (int arg means method
# response code).
class Stream(object):

    def __init__(self, stream_id, conn):
        self.stream_id = stream_id
        # Need to handle cases with push promises.
        self.state = StreamState.IDLE
        self.headers = set()

        self.response = asyncio.Future()

        self._conn = conn

        self._frame_queue = asyncio.Queue()

        self._outgoing_flow_control = 65535
        self._incoming_flow_control = 65535

        # start task to get reponse??

    def add_header_pair(self, header_key, header_value):
        self.headers.add((header_key.lower(), header_value))

    def process_frame(self, frame):
        if isinstance(frame, WindowUpdateFrame):
            self._outgoing_flow_control += frame.window_size_increment
        else:
            self._frame_queue.put(frame)

    def send_data(self, data, end_stream):
        # How to handle outgoing data from stream?
        pass

    @asyncio.coroutine
    def get_response(self):
        # send window update frames for the stream_id once frames are popped
        # off.
        pass

    def close(self):
        pass

    def open(self):
        pass
