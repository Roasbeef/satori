"""
"""
from enum import Enum

import struct
import asyncio
import collections
import io

MAX_FRAME_SIZE = (2 ** 14) - 1


class ErrorCodes(Enum):
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


class FrameFlag(Enum):
    # TODO(roasbeef) need to change this first one, only a settings frame uses
    # this.
    # ACK = 0x0
    # TODO(roasbeef) move this into the PushPromise class
    # END_PUSH_PROMISE = 0x4

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
    def __init__(self, length, frame_type, flags, stream_id):
        self.length = length
        self.frame_type = frame_type
        self.raw_flag_bits = flags
        self.stream_id = stream_id

    def __len__(self):
        """ Return the length of the header's payload, in bytes. """
        return self.length

    def __repr__(self):
        return '<FrameHeader length:{}, frame_type:{}, flags:{}, stream_id:{}>'.format(
            self.length,
            BYTES_TO_FRAME[self.frame_type].__name__,
            '<{}>'.format(','.join(str(flag_type.name) for flag_type in FrameFlag if self.flags & flag_type.value)),
            self.stream_id
        )

    @classmethod
    def from_raw_bytes(cls, frame_bytes):
        header_fields = struct.unpack('!HBBL', frame_bytes)
        # Knock off the first 2 bits, they are reserved, and currently unused.
        payload_length = header_fields[0] & 0x3FFF
        frame_type = header_fields[1]
        raw_flags = header_fields[2]
        stream_id = header_fields[3]

        return cls(payload_length, frame_type, raw_flags, stream_id)

    @classmethod
    def from_frame(cls, frame):
        return cls(len(frame), frame.frame_type, frame.flags, frame.stream_id)

    def serialize(self):
        return struct.pack(
            '!HBBL',
            self.length & 0x3FFF,  # Knock off first two bits.
            self.frame_type,
            self.raw_flag_bits,
            self.stream_id & 0x7FFFFFFF  # Make sure it's 31 bits.
        )


class Frame(object):

    frame_type = None
    defined_flags = None

    def __init__(self, stream_id):
        # Stream_id can never be 0x0, throw error if so.
        # Only the initial response, to an HTTP/1.1 update
        # request can have an identifier of 0x1? or 0x0?
        self.stream_id = stream_id
        self.flags = set()

    def __len__(self):
        raise NotImplementedError

    def __repr__(self):
        pass

    @staticmethod
    def from_frame_header(frame_header):
        frame_klass = BYTES_TO_FRAME[frame_header.frame_type]

        parsed_frame = frame_klass(frame_header.stream_id)
        parsed_frame.parse_flags(frame_header.flags)
        return parsed_frame

    def parse_flags(self, flag_byte):
        for flag_type in self.defined_flags:
            if flag_byte & flag_type.value:
                self.flags.add(flag)

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

    def __len__(self):
        return len(self.data)

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

        self.priority = 0

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

        self.error_code = 0

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
    #defined_flags = FrameFlag.create_flag_set('ACK')

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

        self.settings = {}

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
    #defined_flags = FrameFlag.create_flag_set('END_PUSH_PROMISE')

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
    #defined_flags = FrameFlag.create_flag_set('ACK')

    @classmethod
    def pong_from_ping(ping_frame):
        pass

    def __init__(self, stream_id=0):
        # Again stream_id must be zero
        super().__init__(stream_id)

        self.opaque_data = b''

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

        self.last_stream_id = 0
        self.error_code = 0
        self.debug_data = b''

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

        self.window_size_increment = 0

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

# Maps frame byte type identifiers to its respective class.
BYTES_TO_FRAME = {
    0x0: DataFrame,
    0x1: HeadersFrame,
    0x2: PriorityFrame,
    0x3: RstStreamFrame,
    0x4: SettingsFrame,
    0x5: PushPromise,
    0x6: PingFrame,
    0x7: GoAwayFrame,
    0x8: WindowUpdateFrame,
    0x9: ContinuationFrame
}
