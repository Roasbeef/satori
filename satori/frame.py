"""
"""
from enum import enum

import struct
import asyncio
import collections
import io

MAX_FRAME_SIZE = (2 ** 14) - 1


class ErrorCodes(enum):
    NO_ERROR = 0x0
    PROTOCOL_ERROR = 0x01
    INTERNAL_ERROR = 0x02
    FLOW_CONTROL_ERROR = 0x04
    SETTINGS_TIMEOUT = 0x08
    STREAM_CLOSED = 0x10
    FRAME_SIZE_ERROR = 0x20
    REFUSED_STREAM = 0x40
    CANCEL = 0x80
    COMPRESSION_ERROR = 0x100
    CONNECT_ERROR = 0x200
    ENHANCE_YOUR_CALM = 0x400
    INADEQUATE_SECURITY = 0x800


class FrameFlag(enum):
    ACK = 0x1
    END_STREAM = 0x1
    END_SEGMENT = 0x2
    END_HEADERS = 0x4
    END_PUSH_PROMISE = 0x4
    PRIORITY = 0x8
    PAD_LOW = 0x10
    PAD_HIGH = 0x20

    @staticmethod
    def create_flag_set(*flag_names):
        return {FrameFlag[flag_name] for flag_name in flag_names}


class FrameHeader(object):
    """
     0                   1                   2                   3
     0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
     | R |     Length (14)           |   Type (8)    |   Flags (8)   |
     +-+-+-----------+---------------+-------------------------------+
     |R|                 Stream Identifier (31)                      |
     +-+-------------------------------------------------------------+
     |                   Frame Payload (0...)                      ...
     +---------------------------------------------------------------+
    """
    def __init__(self, length, frame_type, flags, stream_id):
        self.length = length
        self.frame_type = frame_type
        self.flags = flags
        self.stream_id = stream_id

    def __repr__(self):
        pass

    def __str__(self):
        pass

    @classmethod
    def from_raw_bytes(frame_bytes):
        pass

    @classmethod
    def from_frame(frame):
        pass

    def serialize(self):
        pass


class Frame(object):

    frame_type = None

    def __init__(self, stream_id):
        # Stream_id can never be 0x0, throw error if so.
        # Only the initial response, to an HTTP/1.1 update
        # request can have an identifier of 0x1? or 0x0?
        self.stream_id = stream_id
        self.flags = set()

    def __len__(self):
        pass

    def __repr__(self):
        pass

    def __str__(self):
        pass

    @classmethod
    def from_frame_header(self, frame_header):
        pass

    @classmethod
    def from_raw_conn(self, conn):
        pass

    def deserialize(self, frame_payload):
        raise NotImplementedError

    def serialize(self):
        raise NotImplementedError


class DataFrame(Frame):
    """
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    | [Pad High(8)] | [Pad Low (8)] |          Data (*)             .
    +---------------+---------------+-------------------------------+
    .                            Data (*)                         ...
    +---------------------------------------------------------------+
    |                           Padding (*)                       ...
    +---------------------------------------------------------------+
    """

    frame_type = 0x00
    defined_flags = FrameFlag.create_flag_set('END_STREAM', 'END_SEGMENT',
                                              'PAD_LOW', 'PAD_HIGH')

    def __init__(self, stream_id):
        super().__init__(stream_id)

        self.data = b''
        self.pad_high = None
        self.pad_low = None
        self.padding = None

    def deserialize(self, frame_payload):
        pass

    def serialize(self):
        pass


class HeadersFrame(Frame):
    """
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    | [Pad High(8)] | [Pad Low (8)] |X|      [Priority (31)]      ...
    +---------------+---------------+-+-----------------------------+
    ...[Priority]                   | Header Block Fragment (*)   ...
    +-------------------------------+-------------------------------+
    |                   Header Block Fragment (*)                 ...
    +---------------------------------------------------------------+
    |                           Padding (*)                       ...
    +---------------------------------------------------------------+
    """

    frame_type = 0x1
    defined_flags = FrameFlag.create_flag_set('END_STREAM', 'END_SEGMENT',
                                              'END_HEADERS', 'PRIORITY',
                                              'PAD_LOW', 'PAD_HIGH')

    def __init__(self, stream_id):
        super().__init__(stream_id)

        self.priority = None

    def deserialize(self, frame_payload):
        pass

    def serialize(self):
        pass


class PriorityFrame(Frame):
    """
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |X|                        Priority (31)                        |
    +-+-------------------------------------------------------------+
    """
    frame_type = 0x02
    defined_flags = None

    def __init__(self, stream_id):
        super().__init__(stream_id)

    def deserialize(self, frame_payload):
        pass

    def serialize(self):
        pass


class RstStreamFrame(Frame):
    """
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                        Error Code (32)                        |
    +---------------------------------------------------------------+
    """
    frame_type = 0x03
    defined_flags = None

    def __init__(self, stream_id):
        super().__init__(stream_id)

    def deserialize(self, frame_payload):
        pass

    def serialize(self):
        pass


class SettingsFrame(Frame):
    """
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |Identifier (8) |                 Value (32)                  ...
    +---------------+-----------------------------------------------+
    ...Value        |
    +---------------+

    """
    frame_type = 0x04
    defined_flags = FrameFlag.create_flag_set('ACK')

    HEADER_TABLE_SIZE = 0x01
    ENABLE_PUSH = 0x02
    MAX_CONCURRENT_STREAMS = 0x03
    INITIAL_WINDOW_SIZE = 0x04

    FLOW_CONTROL_OPTIONS = None

    def __init__(self, stream_id=0):
        # Stream ID must ALWAYS be zero
        # if stream_id != 0:
        #    raise SomeErrorICreate
        super().__init__(stream_id)

    def deserialize(self, frame_payload):
        pass

    def serialize(self):
        pass


class PushPromise(Frame):
    """
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |X|                Promised-Stream-ID (31)                      |
    +-+-------------------------------------------------------------+
    |                 Header Block Fragment (*)                   ...
    +---------------------------------------------------------------+
    """
    frame_type = 0x5
    defined_flags = FrameFlag.create_flag_set('END_PUSH_PROMISE')

    def __init__(self, stream_id):
        super().__init__(stream_id)

    def deserialize(self, frame_payload):
        pass

    def serialize(self):
        pass


class PingFrame(Frame):
    """
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                                                               |
    |                      Opaque Data (64)                         |
    |                                                               |
    +---------------------------------------------------------------+
    """
    frame_type = 0x6
    defined_flags = FrameFlag.create_flag_set('ACK')

    @classmethod
    def pong_from_ping(ping_frame):
        pass

    def __init__(self, stream_id=0):
        # Again stream_id must be zero
        super().__init__(stream_id)

    def deserialize(self, frame_payload):
        # Length of frame MUST be 8 bytes
        # Raise FrameSizeError if not.
        pass

    def serialize(self):
        pass


class GoAwayFrame(Frame):
    """
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |X|                  Last-Stream-ID (31)                        |
    +-+-------------------------------------------------------------+
    |                      Error Code (32)                          |
    +---------------------------------------------------------------+
    |                  Additional Debug Data (*)                    |
    +---------------------------------------------------------------+
    """

    frame_type = 0x7
    defined_flags = None

    def __init__(self, stream_id=0):
        # Again, must have a stream_id of zero.
        super().__init__(stream_id)

    def deserialize(self, frame_payload):
        pass

    def serialize(self):
        pass


class WindowUpdateFrame(Frame):
    """
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |X|              Window Size Increment (31)                     |
    +-+-------------------------------------------------------------+
    """

    frame_type = 0x8
    defined_flags = None

    def __init__(self, stream_id):
        # If ID is zero, applies to entire stream.
        super().__init__(stream_id)

    def deserialize(self, frame_payload):
        pass

    def serialize(self):
        pass


class ContinuationFrame(Frame):
    """
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    | [Pad High(8)] | [Pad Low (8)] |  Header Block Fragment (*)    .
    +---------------+---------------+-------------------------------+
    |                   Header Block Fragment (*)                 ...
    +---------------------------------------------------------------+
    |                           Padding (*)                       ...
    +---------------------------------------------------------------+
    """
    frame_type = 0x9
    defined_flags = FrameFlag.create_flag_set('PAD_LOW', 'PAD_HIGH',
                                              'END_HEADERS')

    def __int__(self, stream_id):
        # Can't be zero.
        super().__init__(stream_id)

    def deserialize(self, frame_payload):
        pass

    def serialize(self):
        pass
