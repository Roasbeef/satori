"""
"""
from enum import IntEnum, Enum
from .exceptions import ProtocolError, FrameSizeError, FlowControlError

import struct

MAX_FRAME_SIZE = (2 ** 14) - 1
MAX_WINDOW_UPDATE = (2 ** 31) - 1
DEFAULT_PRIORITY = (2 ** 30)


class ConnectionSetting(Enum):
    HEADER_TABLE_SIZE = 0x01
    ENABLE_PUSH = 0x02
    MAX_CONCURRENT_STREAMS = 0x03
    INITIAL_WINDOW_SIZE = 0x04


class FrameType(Enum):
    DATA = 0x00
    HEADERS = 0x1
    PRIORITY = 0x2
    RST_STREAM = 0x3
    SETTINGS = 0x4
    PUSH_PROMISE = 0x5
    PING = 0x6
    GO_AWAY = 0x7
    WINDOW_UPDATE = 0x8
    CONTINUATION = 0x9


class ErrorCode(Enum):
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


# TODO(roasbeef): Think of better name? And/or better way to handle the
# redundancy.
class SpecialFrameFlag(Enum):
    ACK = 0x1
    END_PUSH_PROMISE = 0x4


class FrameFlag(Enum):

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
            FRAME_TYPE_TO_FRAME[self.frame_type].__name__,
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

        return cls(payload_length, FrameType(frame_type), raw_flags, stream_id)

    @classmethod
    def from_frame(cls, frame):
        raw_flags = 0
        for flag_type in frame.flags:
            raw_flags |= flag_type.value

        return cls(len(frame), frame.frame_type, raw_flags, frame.stream_id)

    def serialize(self):
        return struct.pack(
            '!HBBL',
            self.length & 0x3FFF,  # Knock off first two bits.
            self.frame_type.value,
            self.raw_flag_bits,
            self.stream_id & 0x7FFFFFFF  # Make sure it's 31 bits.
        )


class Frame(object):

    frame_type = None
    defined_flags = set()

    def __init__(self, stream_id, flags=None, length=0):
        self.stream_id = stream_id
        self.flags = flags if flags is not None else set()
        self.length = length

    def __len__(self):
        # TODO(roasbeef): Delete this method?
        return self.length

    def __repr__(self):
        return '<{}| length: {}, flags: {}, stream_id: {}, data: {}>'.format(
            FRAME_TYPE_TO_FRAME[self.frame_type].__name__,
            len(self),
            '<{}>'.format(','.join(str(flag_type.name) for flag_type in self.defined_flags if flag_type in self.flags)),
            self.stream_id,
            (self.data if isinstance(self, DataFrame) else b''),
        )

    @staticmethod
    def from_frame_header(frame_header):
        frame_klass = FRAME_TYPE_TO_FRAME[frame_header.frame_type]

        parsed_frame = frame_klass(frame_header.stream_id)
        parsed_frame.parse_flags(frame_header.raw_flag_bits)
        return parsed_frame

    def parse_flags(self, flag_byte):
        for flag_type in self.defined_flags:
            if flag_byte & flag_type.value:
                self.flags.add(flag_type)

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

    frame_type = FrameType.DATA
    defined_flags = FrameFlag.create_flag_set('END_STREAM', 'END_SEGMENT',
                                              'PAD_LOW', 'PAD_HIGH')

    def __init__(self, stream_id, **kwargs):
        if stream_id == 0:
            raise ProtocolError()

        super().__init__(stream_id, **kwargs)

        self.data = b''
        self.pad_high = None
        self.pad_low = None
        self.total_padding = 0

    def __len__(self):
        return 2 + len(self.data) + self.total_padding

    def deserialize(self, frame_payload):
        self.pad_high = frame_payload[0] if FrameFlag.PAD_HIGH in self.flags else 0
        self.pad_low = frame_payload[1] if FrameFlag.PAD_LOW in self.flags else 0

        self.total_padding = (self.pad_high * 256) + self.pad_low
        if self.total_padding > len(frame_payload[2:]):
            raise ProtocolError()

        # TODO(roasbeef): Enforce max frame size, tests and such.
        self.data = frame_payload[2:len(frame_payload) - self.total_padding]

    def serialize(self, pad_low=0, pad_high=0):
        frame_header = FrameHeader.from_frame(self).serialize()

        padding_bytes = ((pad_high * 256) + pad_low) * struct.pack('!x')
        pad_low_and_high = struct.pack('!BB', pad_high, pad_low)

        return frame_header + pad_low_and_high + self.data + padding_bytes


class HeadersFrame(DataFrame):
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
    frame_type = FrameType.HEADERS
    defined_flags = FrameFlag.create_flag_set('END_STREAM', 'END_SEGMENT',
                                              'END_HEADERS', 'PRIORITY',
                                              'PAD_LOW', 'PAD_HIGH')

    def __init__(self, stream_id, priority=None, **kwargs):
        super().__init__(stream_id, **kwargs)

        #self.priority = DEFAULT_PRIORITY if priority is None else priority
        self.priority = None

    def __len__(self):
        return 2 + (4 if self.priority is not None else 0) + len(self.data) + self.total_padding

    def deserialize(self, frame_payload):
        if FrameFlag.PRIORITY in self.flags:
            # Grab the priority, snip off the reserved bit.
            self.priority = struct.unpack('!L', frame_payload[2:6])[0] & 0x7FFFFFFF
            # Slice off the 4 priority bytes, at this point it's like a regular
            # DataFrame payload.
            frame_payload = frame_payload[:2] + frame_payload[6:]

        super().deserialize(frame_payload)

    def serialize(self, pad_low=0, pad_high=0):
        serialized_frame = super().serialize(pad_low, pad_high)
        if FrameFlag.PRIORITY not in self.flags:
            return serialized_frame
        else:
            priority_bytes = struct.pack('!L', self.priority)
            return serialized_frame[:10] + (priority_bytes) + serialized_frame[10:]


class PriorityFrame(Frame):
    """
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |X|                        Priority (31)                        |
    +-+-------------------------------------------------------------+
    """
    frame_type = FrameType.PRIORITY
    defined_flags = None

    def __init__(self, stream_id, **kwargs):
        if stream_id == 0:
            raise ProtocolError()

        super().__init__(stream_id, **kwargs)

        self.priority = 0

    def __len__(self):
        return 4

    def deserialize(self, frame_payload):
        if len(frame_payload) != 4:
            raise ProtocolError()

        self.priority = struct.unpack('!L', frame_payload)[0] & 0x7FFFFFFF

    def serialize(self):
        frame_header = FrameHeader.from_frame(self).serialize()
        return frame_header + struct.pack('!L', self.priority & 0x7FFFFFFF)


class RstStreamFrame(Frame):
    """
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                        Error Code (32)                        |
    +---------------------------------------------------------------+
    """
    frame_type = FrameType.RST_STREAM
    defined_flags = None

    def __init__(self, stream_id, error_code=ErrorCode.NO_ERROR, **kwargs):
        super().__init__(stream_id, **kwargs)

        self.error_code = error_code

    def __len__(self):
        return 4

    def deserialize(self, frame_payload):
        if len(frame_payload) != 4:
            raise ProtocolError()

        try:
            self.error_code = ErrorCode(struct.unpack('!L', frame_payload)[0])
        except ValueError:
            # Not valid code, yatata...
            raise ProtocolError()

    def serialize(self):
        frame_header = FrameHeader.from_frame(self).serialize()
        return frame_header + struct.pack('!L', self.error_code.value)


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
    frame_type = FrameType.SETTINGS
    defined_flags = {SpecialFrameFlag.ACK}

    def __init__(self, stream_id=0, settings=None, **kwargs):
        if stream_id != 0:
            raise ProtocolError()

        self.settings = {} if settings is None else settings
        super().__init__(stream_id, **kwargs)

    def __len__(self):
        if SpecialFrameFlag.ACK in self.flags:
            return 0
        else:
            # 5 bytes per setting.
            return len(self.settings) * 5

    @property
    def is_ack(self):
        return SpecialFrameFlag.ACK in self.flags

    def deserialize(self, frame_payload):
        # A settings ACK frame must have no data.
        if SpecialFrameFlag.ACK in self.flags and len(frame_payload):
            raise FrameSizeError()

        # Process a frame at a time by splitting up into 5 byte chunks.
        settings_chunks = (frame_payload[i:i + 5] for i in range(0, len(frame_payload), 5))
        for setting_chunk in settings_chunks:
            # TODO(roasbeef): Make sure flow control size value isn't above
            # 2^31-1
            setting_key = setting_chunk[0]
            setting_value = struct.unpack('!L', setting_chunk[1:])[0]

            try:
                self.settings[ConnectionSetting(setting_key)] = setting_value
            except ValueError:
                raise ProtocolError()

    def serialize(self):
        # TODO(roasbeef): Use bytearray everywhere or output with b''.joins?
        settings_header = FrameHeader.from_frame(self).serialize()

        settings = []
        settings.append(settings_header)

        for setting_key, setting_value in self.settings.items():
            settings.append(struct.pack('!BL', setting_key.value, setting_value))

        return b''.join(settings)


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
    frame_type = FrameType.PUSH_PROMISE
    # TODO(roasbeef): If this is NOT set, then the next frame on the
    # promised_stream_id MUST be a ContinuationFrame.
    defined_flags = {SpecialFrameFlag.END_PUSH_PROMISE}

    def __init__(self, stream_id, **kwargs):
        # TODO(roasbeef): Stream id must also be assoicated with some other
        # existing stream.
        if stream_id == 0:
            raise ProtocolError()

        super().__init__(stream_id, **kwargs)

        self.promised_stream_id = 0
        self.data = b''

    def __len__(self):
        return 4 + len(self.data)

    def deserialize(self, frame_payload):
        self.promised_stream_id = struct.unpack('!L', frame_payload[:4])[0] & 0x7FFFFFFF
        self.data = frame_payload[4:]

    def serialize(self):
        frame_header = FrameHeader.from_frame(self).serialize()
        payload = struct.pack('!L', self.promised_stream_id & 0x7FFFFFFF) + self.data

        return frame_header + payload


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
    frame_type = FrameType.PING
    defined_flags = {SpecialFrameFlag.ACK}

    @classmethod
    def pong_from_ping(cls, ping_frame):
        pong = cls(ping_frame.stream_id, flags={SpecialFrameFlag.ACK})
        pong.deserialize(ping_frame.opaque_data)
        return pong

    def __len__(self):
        return 8

    def __init__(self, stream_id=0, **kwargs):
        # Again stream_id must be zero
        if stream_id != 0:
            raise ProtocolError()

        super().__init__(stream_id, **kwargs)

        self.opaque_data = b''

    def deserialize(self, frame_payload):
        if len(frame_payload) != 8:
            raise FrameSizeError()

        self.opaque_data = frame_payload

    def serialize(self):
        frame_header = FrameHeader.from_frame(self).serialize()
        return frame_header + self.opaque_data


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

    frame_type = FrameType.GO_AWAY
    defined_flags = set()

    def __init__(self, stream_id=0, **kwargs):
        if stream_id != 0:
            raise ProtocolError()

        super().__init__(stream_id, **kwargs)

        # TODO(roasbeef): Make something like this consistent with all other
        # framing data structures.
        self.last_stream_id = kwargs.get('last_stream_id', 0)
        self.error_code = kwargs.get('error_code', 0)
        self.debug_data = kwargs.get('debug_data', b'')

    def __len__(self):
        return 8 + len(self.debug_data)

    def deserialize(self, frame_payload):
        self.last_stream_id = struct.unpack('!L', frame_payload[:4])[0] & 0x7FFFFFFF

        try:
            self.error_code = ErrorCode(struct.unpack('!L', frame_payload[4:8])[0])
        except ValueError:
            raise ProtocolError()

        self.debug_data = frame_payload[8:]

    def serialize(self):
        frame_header = FrameHeader.from_frame(self).serialize()
        return frame_header + struct.pack('!LL', self.last_stream_id & 0x7FFFFFFF, self.error_code.value) + self.debug_data


class WindowUpdateFrame(Frame):
    """
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |X|              Window Size Increment (31)                     |
    +-+-------------------------------------------------------------+
    """

    frame_type = FrameType.WINDOW_UPDATE
    defined_flags = set()

    def __init__(self, stream_id, **kwargs):
        # TODO(roasbeef): Make all __init__ methods uniform.
        self.connection_update = True if stream_id == 0 else False
        self.window_size_increment = kwargs.pop('window_size_increment', 0) & 0x7FFFFFFF

        # If ID is zero, applies to entire stream.
        super().__init__(stream_id, **kwargs)

    def __len__(self):
        return 4

    def deserialize(self, frame_payload):
        if len(frame_payload) != 4:
            raise ProtocolError()
        else:
            window_increment = struct.unpack('!L', frame_payload)[0]
            if window_increment > MAX_WINDOW_UPDATE:
                raise FlowControlError()

            self.window_size_increment = window_increment

    def serialize(self):
        frame_header = FrameHeader.from_frame(self).serialize()
        return frame_header + struct.pack('!L', self.window_size_increment)


class ContinuationFrame(DataFrame):
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
    frame_type = FrameType.CONTINUATION
    defined_flags = FrameFlag.create_flag_set('PAD_LOW', 'PAD_HIGH',
                                              'END_HEADERS')

# Maps members of the FrameType Enum, to its respective class object.
FRAME_TYPE_TO_FRAME = {
    FrameType.DATA: DataFrame,
    FrameType.HEADERS: HeadersFrame,
    FrameType.PRIORITY: PriorityFrame,
    FrameType.RST_STREAM: RstStreamFrame,
    FrameType.SETTINGS: SettingsFrame,
    FrameType.PUSH_PROMISE: PushPromise,
    FrameType.PING: PingFrame,
    FrameType.GO_AWAY: GoAwayFrame,
    FrameType.WINDOW_UPDATE: WindowUpdateFrame,
    FrameType.CONTINUATION: ContinuationFrame
}
