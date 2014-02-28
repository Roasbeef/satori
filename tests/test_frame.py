import unittest
import struct

from satori.frame import (FrameHeader, FrameType, FrameFlag, Frame, DataFrame,
                          ProtocolError, HeadersFrame, PriorityFrame, RstStreamFrame,
                          ErrorCode, SettingsFrame, SpecialFrameFlag, FrameSizeError,
                          ConnectionSetting, PushPromise, PingFrame, GoAwayFrame,
                          FlowControlError, WindowUpdateFrame)


padding_bytes = lambda n: struct.pack('!x') * n


class TestFrameHeader(unittest.TestCase):

    def setUp(self):
        self.basic_test_bytes = b'\x00\x08\x00\x01\x00\x00\x00\x01'

    def test_from_raw_bytes(self):
        # DataFrame header, 8bytes length, END_STREAM flag, first stream.
        header = FrameHeader.from_raw_bytes(self.basic_test_bytes)

        self.assertEqual(8, len(header))
        self.assertEqual(FrameType.DATA.value, header.frame_type)
        self.assertEqual(FrameFlag.END_STREAM.value, header.raw_flag_bits)
        self.assertEqual(1, header.stream_id)

    def test_from_frame(self):
        frame = DataFrame(stream_id=20, flags={FrameFlag.END_STREAM, FrameFlag.PAD_LOW})
        frame_header = FrameHeader.from_frame(frame)
        self.assertEqual(frame_header.length, 2)  # Padding low + high fields
        self.assertEqual(frame_header.frame_type, FrameType.DATA)
        self.assertEqual(frame_header.stream_id, 20)
        self.assertEqual(frame_header.raw_flag_bits,
                         FrameFlag.END_STREAM.value | FrameFlag.PAD_LOW.value)

    def test_serialize(self):
        header = FrameHeader(8, FrameType.DATA, 1, 1)
        self.assertEqual(header.serialize(), self.basic_test_bytes)


class TestFrame(unittest.TestCase):

    def test_from_frame_header(self):
        frame_header = FrameHeader(length=2,
                                   frame_type=FrameType.HEADERS,
                                   flags=(FrameFlag.END_STREAM.value | FrameFlag.END_HEADERS.value),
                                   stream_id=512)

        frame = Frame.from_frame_header(frame_header)
        self.assertEqual(512, frame.stream_id)
        self.assertEqual(2, len(frame))
        self.assertEqual({FrameFlag.END_STREAM, FrameFlag.END_HEADERS}, frame.flags)
        self.assertEqual(FrameType.HEADERS, frame.frame_type)

    def test_parse_flags(self):
        frame = Frame(stream_id=2)
        frame.parse_flags(FrameFlag.PAD_LOW.value | FrameFlag.PAD_HIGH.value | FrameFlag.END_STREAM.value)
        self.assertEqual(set(), frame.flags)


class TestDataFrame(unittest.TestCase):
    def setUp(self):
        self.payload_no_padding = struct.pack('!BB', 0, 0) + b'look ma no padding'
        self.payload_with_low_padding = struct.pack('!BB', 1, 4) + b'low padding' + padding_bytes(4)
        self.payload_with_high_padding = struct.pack('!BB', 1, 0) + b'high padding' + padding_bytes(256)
        self.payload_with_both_padding = struct.pack('!BB', 1, 1) + b'both padding' + padding_bytes(257)
        self.payload_incorrect_padding_value = struct.pack('!BB', 2, 1) + b'bad padding' + padding_bytes(1)

    def test_deserialize_no_padding(self):
        data_frame = DataFrame(1)
        data_frame.deserialize(self.payload_no_padding)
        self.assertEqual(data_frame.data, b'look ma no padding')

    def test_deserialize_with_low_padding(self):
        data_frame = DataFrame(stream_id=1, flags={FrameFlag.PAD_LOW})
        data_frame.deserialize(self.payload_with_low_padding)
        self.assertEqual(data_frame.data, b'low padding')

    def test_deserialize_with_high_padding(self):
        data_frame = DataFrame(stream_id=1, flags={FrameFlag.PAD_HIGH})
        data_frame.deserialize(self.payload_with_high_padding)
        self.assertEqual(data_frame.data, b'high padding')

    def test_deserialize_with_both_padding(self):
        data_frame = DataFrame(stream_id=1, flags={FrameFlag.PAD_HIGH, FrameFlag.PAD_LOW})
        data_frame.deserialize(self.payload_with_both_padding)
        self.assertEqual(data_frame.data, b'both padding')

    def test_deserialize_total_padding_incorrect(self):
        data_frame = DataFrame(stream_id=1, flags={FrameFlag.PAD_HIGH, FrameFlag.PAD_LOW})
        self.assertRaises(ProtocolError, data_frame.deserialize, self.payload_incorrect_padding_value)

    def test_serialize(self):
        data_frame = DataFrame(stream_id=1)
        data_frame.deserialize(self.payload_no_padding)

        frame_bytes = data_frame.serialize()
        self.assertEqual(b'\x00\x14\x00\x00\x00\x00\x00\x01\x00\x00look ma no padding', frame_bytes)

    def test_serialize_with_padding(self):
        data_frame = DataFrame(stream_id=1)
        data_frame.deserialize(self.payload_no_padding)

        frame_bytes = data_frame.serialize(pad_low=1)
        self.assertEqual(b'\x00\x14\x00\x00\x00\x00\x00\x01\x00\x01look ma no padding\x00', frame_bytes)


class TestHeadersFrame(unittest.TestCase):
    # TODO(roasbeef): Also add padding tests? Or redundant since inherited from
    # DataFrame?
    def setUp(self):
        self.maxDiff = None
        self.payload_no_priority = struct.pack('!BB', 0, 0) + b'headers headers'
        self.payload_with_priority = struct.pack('!BBL', 0, 0, 1000) + b'houston, we have priority'

    def test_deserialize_without_priority(self):
        headers_frame = HeadersFrame(1)
        headers_frame.deserialize(self.payload_no_priority)

        self.assertEqual(headers_frame.data, b'headers headers')

    def test_deserialize_with_priority(self):
        headers_frame = HeadersFrame(1, flags={FrameFlag.PRIORITY})
        headers_frame.deserialize(self.payload_with_priority)

        self.assertEqual(headers_frame.priority, 1000)
        self.assertEqual(headers_frame.data, b'houston, we have priority')

    def test_serialize_without_priority(self):
        headers_frame = HeadersFrame(1)
        headers_frame.deserialize(self.payload_no_priority)

        frame_bytes = headers_frame.serialize()
        self.assertEqual(b'\x00\x11\x01\x00\x00\x00\x00\x01\x00\x00headers headers', frame_bytes)

    def test_serialize_with_priority(self):
        headers_frame = HeadersFrame(1, flags={FrameFlag.PRIORITY})
        headers_frame.deserialize(self.payload_with_priority)

        frame_bytes = headers_frame.serialize()
        self.assertEqual(b'\x00\x1f\x01\x08\x00\x00\x00\x01\x00\x00\x00\x00\x03\xe8houston, we have priority', frame_bytes)


class TestPriorityFrame(unittest.TestCase):
    def setUp(self):
        self.test_payload = struct.pack('!L', 1000)

    def test_deserialize(self):
        priority_frame = PriorityFrame(stream_id=1)
        priority_frame.deserialize(self.test_payload)

        self.assertEqual(1000, priority_frame.priority)

    def test_serialize(self):
        priority_frame = PriorityFrame(stream_id=1)
        priority_frame.deserialize(self.test_payload)

        frame_bytes = priority_frame.serialize()

        # TODO(roasbeef): Use the enums instead of raw byte strings in all
        # tests?
        self.assertEqual(b'\x00\x04\x02\x00\x00\x00\x00\x01\x00\x00\x03\xe8', frame_bytes)


class TestRstStreamFrame(unittest.TestCase):
    def setUp(self):
        self.test_payload = struct.pack('!L', ErrorCode.ENHANCE_YOUR_CALM.value)

    def test_deserialize(self):
        rst_stream_frame = RstStreamFrame(stream_id=10)
        rst_stream_frame.deserialize(self.test_payload)

        self.assertEqual(ErrorCode.ENHANCE_YOUR_CALM, rst_stream_frame.error_code)

    def test_serialize(self):
        rst_stream_frame = RstStreamFrame(stream_id=1)
        rst_stream_frame.deserialize(self.test_payload)

        frame_bytes = rst_stream_frame.serialize()
        self.assertEqual(b'\x00\x04\03\x00\x00\x00\x00\x01\x00\x00\x04\x00', frame_bytes)


class TestSettingsFrame(unittest.TestCase):
    def setUp(self):
        self.test_invalid_ack_payload = struct.pack('!BL', 30, 500)
        self.test_all_settings = struct.pack('!BLBLBLBL',
                                             ConnectionSetting.HEADER_TABLE_SIZE.value, 2000,
                                             ConnectionSetting.ENABLE_PUSH.value, 0,
                                             ConnectionSetting.MAX_CONCURRENT_STREAMS.value, 200,
                                             ConnectionSetting.INITIAL_WINDOW_SIZE.value, 30000)
        self.test_single_setting = struct.pack('!BL',
                                               ConnectionSetting.INITIAL_WINDOW_SIZE.value, 30000)

    def test_stream_id_not_1(self):
        self.assertRaises(ProtocolError, SettingsFrame, 1)

    def test_deserialize_settings_ack_with_payload(self):
        settings_frame = SettingsFrame(stream_id=0, flags={SpecialFrameFlag.ACK})
        self.assertRaises(FrameSizeError, settings_frame.deserialize,
                          self.test_invalid_ack_payload)

    def test_deserialize_settings_ack(self):
        settings_frame = SettingsFrame(stream_id=0, flags={SpecialFrameFlag.ACK})
        settings_frame.deserialize(b'')

        self.assertEqual({}, settings_frame.settings)
        self.assertEqual({SpecialFrameFlag.ACK}, settings_frame.flags)

    def test_deserialize(self):
        settings_frame = SettingsFrame(stream_id=0)
        settings_frame.deserialize(self.test_all_settings)

        self.assertEqual(settings_frame.settings[ConnectionSetting.HEADER_TABLE_SIZE], 2000)
        self.assertEqual(settings_frame.settings[ConnectionSetting.ENABLE_PUSH], 0)
        self.assertEqual(settings_frame.settings[ConnectionSetting.MAX_CONCURRENT_STREAMS], 200)
        self.assertEqual(settings_frame.settings[ConnectionSetting.INITIAL_WINDOW_SIZE], 30000)

    def test_serialize_settings_ack(self):
        settings_frame = SettingsFrame(stream_id=0, flags={SpecialFrameFlag.ACK})
        settings_frame.deserialize(b'')

        frame_bytes = settings_frame.serialize()
        self.assertEqual(b'\x00\x00\x04\x01\x00\x00\x00\x00', frame_bytes)

    def test_serialize_settings(self):
        settings_frame = SettingsFrame(stream_id=0)
        settings_frame.deserialize(self.test_single_setting)

        frame_bytes = settings_frame.serialize()
        self.assertEqual(b'\x00\x05\x04\x00\x00\x00\x00\x00\x04\x00\x00\x75\x30', frame_bytes)


class TestPushPromiseFrame(unittest.TestCase):
    def setUp(self):
        self.test_promise_payload = struct.pack('!L', 4444) + b'promised stuff'

    def test_deserialize(self):
        promise_frame = PushPromise(stream_id=1)
        promise_frame.deserialize(self.test_promise_payload)

        self.assertEqual(promise_frame.promised_stream_id, 4444)
        self.assertEqual(promise_frame.data, b'promised stuff')

    def test_serialize(self):
        promise_frame = PushPromise(stream_id=1, flags={SpecialFrameFlag.END_PUSH_PROMISE})
        promise_frame.deserialize(self.test_promise_payload)

        frame_bytes = promise_frame.serialize()

        self.assertEqual(b'\x00\x12\x05\x04\x00\x00\x00\x01\x00\x00\x11\x5cpromised stuff', frame_bytes)


class TestPingFrame(unittest.TestCase):
    def setUp(self):
        self.test_data = struct.pack('!Q', 90000)

    def test_deserialize_not_8_bytes(self):
        ping = PingFrame(stream_id=0)
        self.assertRaises(FrameSizeError, ping.deserialize, b'wrong stuff')

    def test_deserialize(self):
        ping = PingFrame(stream_id=0)
        ping.deserialize(self.test_data)

        self.assertEqual(ping.opaque_data, struct.pack('!Q', 90000))

    def test_serialize(self):
        ping = PingFrame(stream_id=0)
        ping.deserialize(self.test_data)

        self.assertEqual(b'\x00\x08\x06\x00\x00\x00\x00\x00', ping.serialize()[:-8])

    def test_pong_from_ping(self):
        ping = PingFrame(stream_id=0)
        ping.deserialize(self.test_data)

        pong = PingFrame.pong_from_ping(ping)
        self.assertEqual(pong.stream_id, ping.stream_id)
        self.assertEqual(pong.opaque_data, ping.opaque_data)


class TestGoAwayFram(unittest.TestCase):
    def setUp(self):
        self.payload_invalid_error_code = struct.pack(b'!LL', 0, 231) + b'bugs'
        self.payload = struct.pack(b'!LL', 64, ErrorCode.ENHANCE_YOUR_CALM.value) + b'logs n stuff'

    def test_deserialize_invalid_error_code(self):
        go_away = GoAwayFrame(stream_id=0)
        self.assertRaises(ProtocolError, go_away.deserialize, self.payload_invalid_error_code)

    def test_deserialize(self):
        go_away = GoAwayFrame(stream_id=0)
        go_away.deserialize(self.payload)

        self.assertEqual(go_away.last_stream_id, 64)
        self.assertEqual(go_away.error_code, ErrorCode.ENHANCE_YOUR_CALM)
        self.assertEqual(go_away.debug_data, b'logs n stuff')

    def test_serialize(self):
        go_away = GoAwayFrame(stream_id=0)
        go_away.deserialize(self.payload)

        frame_bytes = go_away.serialize()
        self.assertEqual(b'\x00\x14\x07\x00\x00\x00\x00\x00\x00\x00\x00\x40\x00\x00\x04\x00logs n stuff', frame_bytes)


class TestWindowUpdateFrame(unittest.TestCase):
    def setUp(self):
        self.payload_window_too_large = struct.pack('!L', 2 ** 31)
        self.payload = struct.pack('!L', 256)

    def test_deserialize_window_size_too_large(self):
        frame = WindowUpdateFrame(stream_id=0)
        self.assertRaises(FlowControlError, frame.deserialize, self.payload_window_too_large)

    def test_deserialize(self):
        frame = WindowUpdateFrame(stream_id=0)
        frame.deserialize(self.payload)

        self.assertEqual(frame.window_size_increment, 256)

    def test_serialize(self):
        frame = WindowUpdateFrame(stream_id=0, window_size_increment=16)
        frame_bytes = frame.serialize()

        self.assertEqual(b'\x00\x04\x08\x00\x00\x00\x00\x00\x00\x00\x00\x10', frame_bytes)


if __name__ == "__main__":
    unittest.main()
