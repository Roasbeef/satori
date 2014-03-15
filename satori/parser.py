from .frame import FrameHeader, Frame, FrameType
import asyncio
import itertools


class PriorityFrameQueue(object):
    def __init__(self, conn):
        self._conn = conn
        # List to be 'heapified'.
        self._frame_queue = []
        self._frame_indexes = {}
        self._entry_counter = itertools.count()

    def get_frame(self):
        pass

    def put_frame(self, frame):
        pass

class FrameWriter(object):
    def __init__(self, writer, conn):
        self.writer = writer
        self._outgoing_queue = None
        self._conn = conn

    @asyncio.coroutine
    def write_frames(self):
        pass

class FrameReader(object):
    def __init__(self, reader, conn):
        self.reader = reader
        self._incoming_queue = None
        self._conn = conn

    @asyncio.coroutine
    def read_frame(self, header_length=8):
        while True:
            # Need to be wrapped in some try/accept

            # Grab the header first.
            header_bytes = yield from self.reader.read(header_length)
            frame_header = FrameHeader.from_raw_bytes(header_bytes)

            # Read the remainder of the frame payload.
            payload_bytes = yield from self.reader.read(frame_header.length)
            frame = Frame.from_frame_header(frame_header)
            frame.deserialize(payload_bytes)

            subject_to_flow_control = frame.frame_type == FrameType.DataFrame

            # Push the frame unto the heapq
            # Pop off the next one, tuple (frame, is_flow_control)

            # Kick out the frame itself, along with boolean telling the outside world if
            # the frame needs to be flow controlled.
            return frame, subject_to_flow_control
