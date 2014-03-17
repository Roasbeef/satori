from .frame import (FrameHeader, Frame, DataFrame, DEFAULT_PRIORITY,
                    HeadersFrame)

import asyncio
import itertools
import heapq
import collections
import logging

logger = logging.getLogger('http2')
logger.setLevel(logging.INFO)

FrameEntry = collections.namedtuple('FrameEntry', ['priority', 'count', 'frame'])


class PriorityFrameQueue(object):
    REMOVED = '<gone>'

    def __init__(self):
        # List to be 'heapified'.
        self._frame_queue = []
        self._frame_index = {}
        self._entry_counter = itertools.count()

    def push_pop_frame(self, frame, priority):
        """ Push a new frame into the heap, return the new min priority frame."""
        frame_entry = FrameEntry(priority, next(self._entry_counter), frame)
        return heapq.heappushpop(self._frame_queue, frame_entry).frame

    def pop_frame(self):
        while self._frame_queue:
            frame_entry = heapq.heappop(self._frame_queue)
            if frame_entry.frame is not self.REMOVED:
                del self._frame_index[frame_entry.frame]
                return frame_entry.frame

    def push_frame(self, frame, priority):
        frame_entry = FrameEntry(priority, next(self._entry_counter), frame)
        if frame_entry.frame in self._frame_index:
            self.delete_frame(frame_entry.frame)

        self._frame_index[frame] = frame_entry

        heapq.heappush(self._frame_queue, frame_entry)

    def delete_frame(self, frame):
        frame_entry = self._frame_index.pop(frame)
        frame_entry[-1] = self.REMOVED

    def reprioritize_stream(self, stream_id):
        pass


class FrameParser(object):
    def __init__(self, reader, conn):
        self.reader = reader
        self._frame_queue = PriorityFrameQueue()
        self._conn = conn

    @asyncio.coroutine
    def read_frame(self, header_length=8):
        logging.info('Reading a frame')
        # Need to be wrapped in some try/accept

        # Grab the header first.
        header_bytes = yield from self.reader.read(header_length)
        frame_header = FrameHeader.from_raw_bytes(header_bytes)

        # Read the remainder of the frame payload.
        payload_bytes = yield from self.reader.read(frame_header.length)
        frame = Frame.from_frame_header(frame_header)
        frame.deserialize(payload_bytes)

        logging.info('READ FRAME FROM SOCKET: %s' % frame)

        try:
            stream_priority = self._conn._streams[frame.stream_id].priority
        except KeyError:
            stream_priority = DEFAULT_PRIORITY

        logging.info('Frame has priority: %s' % stream_priority)
        prioritized_frame = self._frame_queue.push_pop_frame(frame, stream_priority)

        logging.info('Passing up frame: %s' % frame)
        return prioritized_frame
