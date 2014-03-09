from .frame import FrameHeader, Frame, FrameType
import asyncio


class FrameParser(object):
    def __init__(self, reader):
        self.reader = reader
        self._incoming_queue = None

    @asyncio.coroutine
    def read_frame(self, num_bytes=8):
        while True:
            # Need to be wrapped in some try/accept

            # Grab the header first.
            header_bytes = yield from self.reader.read(num_bytes)
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
