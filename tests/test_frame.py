import unittest

from satori.frame import FrameHeader, FrameType, FrameFlag, Frame


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
        frame = Frame(stream_id=20, flags={FrameFlag.END_STREAM}, length=4)
        frame_header = FrameHeader.from_frame(frame)
        self.assertEqual(frame_header.length, 4)
        self.assertEqual(frame_header.frame_type, None)
        self.assertEqual(frame_header.stream_id, 20)
        self.assertEqual(frame_header.raw_flag_bits, FrameFlag.END_STREAM.value)

    def test_serialize(self):
        header = FrameHeader(8, 0, 1, 1)
        self.assertEqual(header.serialize(), self.basic_test_bytes)


class TestFrame(unittest.TestCase):
    pass

if __name__ == "__main__":
    unittest.main()
