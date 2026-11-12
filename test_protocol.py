import unittest

import protocol


class CodecTest(unittest.TestCase):
    def test_matches_captured_command_and_response_frames(self):
        self.assertEqual(protocol.make_packet(0xA3, b"\0"), protocol.CMD_GET_DEV_STATE)
        self.assertEqual(protocol.make_packet(0xA3, bytes.fromhex("04 0c 29")),
                         bytes.fromhex("51 78 a3 00 03 00 04 0c 29 88 ff"))
        frame = bytes.fromhex("51 78 a3 01 03 00 04 0c 29 88 ff")
        self.assertEqual(protocol.parse_state(frame)["flags"], 4)
        self.assertEqual(protocol.crc8(frame[6:-2]), frame[-2])

    def test_crc_standard_check_vector(self):
        self.assertEqual(protocol.crc8(b"123456789"), 0xF4)

    def test_binary_raster_packet_preserves_payload(self):
        row = bytes(range(48))
        packet = protocol.make_packet(0xA2, row)
        self.assertEqual(packet[:6], bytes.fromhex("51 78 a2 00 30 00"))
        self.assertEqual(packet[6:-2], row)


if __name__ == "__main__":
    unittest.main()
