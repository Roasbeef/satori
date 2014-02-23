import unittest

from satori.frame import FrameHeader


class TestFrameHeader(unittest.TestCase):
    def setUp(self):
        self.basic_test_bytes = b'\x00\x08\x00\x01\x00\x00\x00\x01'

    def test_from_raw_bytes(self):
        # DataFrame header, 8bytes length, all flags, first stream.
        header = FrameHeader.from_raw_bytes(self.basic_test_bytes)

        self.assertEqual(8, len(header))
        self.assertEqual(0x0, header.frame_type)
        self.assertEqual(1, header.raw_flag_bits)
        self.assertEqual(1, header.stream_id)

    def test_from_frame(self):
        pass

    def test_serialize(self):
        header = FrameHeader(8, 0, 1, 1)
        self.assertEqual(header.serialize(), self.basic_test_bytes)


class TestFrame(unittest.TestCase):
    pass

if __name__ == "__main__":
    unittest.main()
