"""
"""
from enum import enum

import struct
import asyncio
import collections
import io

MAX_FRAME_SIZE = (2 ** 14) - 1


class FrameFlag(enum):
    ACK = 0x1
    END_STREAM = 0x1
    END_SEGMENT = 0x2
    END_HEADERS = 0x4
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
    def __init__(self):
        pass

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

    frame_type = 0x01
    defined_flags = FrameFlag.create_flag_set('END_STREAM', 'END_SEGMENT',
                                              'END_HEADERS', 'PRIORITY',
                                              'PAD_LOW', 'PAD_HIGH')

    def __init__(self, stream_id):
        super().__init__(stream_id)

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
    defined_flags = Frame.create_flag_set('ACK')

    HEADER_TABLE_SIZE = 0x01
    ETTINGS_ENABLE_PUSH = 0x02
    MAX_CONCURRENT_STREAMS = 0x03
    INGS_INITIAL_WINDOW_SIZE = 0x04
    FLOW_CONTROL_OPTIONS = None

    def __init__(self, stream_id):
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
