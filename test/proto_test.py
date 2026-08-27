#!/usr/bin/env python3
"""Framing and CRC, covered without hardware.

`proto.py` is pure -- crc16_modbus, build and frames take bytes and return
bytes -- so the wire format can be pinned down with the headphones switched
off, or absent entirely.

This suite is written *before* the move to `src/` and must go on passing after
it, unedited. That is the whole point: a test adjusted to accommodate a
refactor proves the refactor, not the behaviour.

Fixtures are real frames lifted from `capture.log`, not hand-authored. A
hand-typed frame only proves the code agrees with whoever typed it.
"""
import pathlib
import sys
import unittest

# proto.py moves from the repo root to src/cmfctl/ in T2, so resolve it in
# either layout rather than hardcoding one. Both candidates are added because
# the flat layout has no src/, and the package layout no longer has a
# top-level proto.py.
_ROOT = pathlib.Path(__file__).resolve().parent.parent
for _candidate in (_ROOT, _ROOT / "src"):
    if _candidate.is_dir():
        sys.path.insert(0, str(_candidate))

try:
    from cmfctl import proto          # src/ layout, from T2 onwards
except ImportError:                   # pragma: no cover - only one arm runs
    import proto                      # flat layout, before T2


# A real reply captured on RFCOMM 28, CRC flag set. Byte for byte:
#   55 60 01 | 41 40 | 01 00 | ff | 00 | 91 99
#   sync flags target  cmd LE  len LE  fsn  payload  crc LE
# The log line beside it in capture.log annotates cmd as 0x4140; that
# annotation predates the byte order being settled and the raw bytes win.
CAPTURED_CRC_FRAME = bytes.fromhex("55600141400100ff009199")
CAPTURED_CRC_VALUE = 0x9991
CAPTURED_CRC_CMD = 0x4041

# A battery notification, sent unprompted by the device with the CRC flag
# clear. Payload 01 06 37 -- the trailing 0x37 is 55, the charge level the
# README quotes.
CAPTURED_BATTERY_FRAME = bytes.fromhex("55000301e0030000010637")
EVENT_BATTERY_CHANGED = 0xE001


class Crc(unittest.TestCase):
    def test_matches_a_captured_frame(self):
        """The CRC we compute is the CRC the device actually sent."""
        body = CAPTURED_CRC_FRAME[:-proto.CRC_LEN]
        self.assertEqual(proto.crc16_modbus(body), CAPTURED_CRC_VALUE)

    def test_empty_input_is_the_seed(self):
        """CRC-16/MODBUS starts at 0xFFFF, so no bytes means no change."""
        self.assertEqual(proto.crc16_modbus(b""), 0xFFFF)

    def test_a_single_flipped_bit_changes_it(self):
        body = bytearray(CAPTURED_CRC_FRAME[:-proto.CRC_LEN])
        body[-1] ^= 0x01
        self.assertNotEqual(proto.crc16_modbus(bytes(body)), CAPTURED_CRC_VALUE)


class Build(unittest.TestCase):
    def test_reproduces_a_captured_frame_exactly(self):
        """Our encoder and the real device agree, byte for byte.

        The strongest check in this file: it pins framing, both little-endian
        fields and the CRC against hardware output rather than against us.
        """
        self.assertEqual(
            proto.build(CAPTURED_CRC_CMD, b"\x00", fsn=0xFF, target=0x01),
            CAPTURED_CRC_FRAME,
        )

    def test_roundtrip_empty_payload(self):
        self._assert_roundtrip(0x1234, b"")

    def test_roundtrip_single_byte_payload(self):
        self._assert_roundtrip(0x4041, b"\x07")

    def test_roundtrip_multi_byte_payload(self):
        self._assert_roundtrip(0xABCD, bytes(range(16)))

    def test_length_field_is_the_payload_length(self):
        frame = proto.build(0x0001, b"\x01\x02\x03")
        self.assertEqual(len(frame), proto.HDR_LEN + 3 + proto.CRC_LEN)

    def _assert_roundtrip(self, cmd, payload, fsn=0x2A):
        decoded = list(proto.frames(proto.build(cmd, payload, fsn=fsn)))
        self.assertEqual(len(decoded), 1)
        self.assertEqual(decoded[0], (cmd, fsn, payload, True))


class Frames(unittest.TestCase):
    def test_decodes_a_captured_notification(self):
        decoded = list(proto.frames(CAPTURED_BATTERY_FRAME))
        self.assertEqual(len(decoded), 1)
        cmd, _fsn, payload, crc_ok = decoded[0]
        self.assertEqual(cmd, EVENT_BATTERY_CHANGED)
        self.assertIsNone(crc_ok)
        self.assertEqual(payload[-1], 55)

    def test_absent_crc_is_none_not_false(self):
        """`None` means "not claimed", `False` means "claimed and wrong".

        Collapsing them would let a corrupted frame read as merely unverified.
        """
        (_, _, _, crc_ok), = proto.frames(CAPTURED_BATTERY_FRAME)
        self.assertIsNone(crc_ok)
        self.assertIsNot(crc_ok, False)

    def test_corrupt_crc_is_reported(self):
        corrupt = bytearray(CAPTURED_CRC_FRAME)
        corrupt[-1] ^= 0xFF
        (_, _, _, crc_ok), = proto.frames(bytes(corrupt))
        self.assertIs(crc_ok, False)

    def test_corrupt_payload_is_reported(self):
        """The CRC covers the payload, not just the header."""
        corrupt = bytearray(CAPTURED_CRC_FRAME)
        corrupt[proto.HDR_LEN] ^= 0xFF
        (_, _, _, crc_ok), = proto.frames(bytes(corrupt))
        self.assertIs(crc_ok, False)

    def test_two_concatenated_frames_yield_both(self):
        """The streaming case: a single read can carry more than one frame."""
        buf = CAPTURED_CRC_FRAME + CAPTURED_BATTERY_FRAME
        decoded = list(proto.frames(buf))
        self.assertEqual(len(decoded), 2)
        self.assertEqual(decoded[0][0], CAPTURED_CRC_CMD)
        self.assertEqual(decoded[1][0], EVENT_BATTERY_CHANGED)

    def test_truncated_payload_yields_nothing(self):
        """A short read is normal on a stream and must not raise."""
        self.assertEqual(list(proto.frames(CAPTURED_CRC_FRAME[:-3])), [])

    def test_shorter_than_a_header_yields_nothing(self):
        self.assertEqual(list(proto.frames(CAPTURED_CRC_FRAME[:4])), [])

    def test_empty_buffer_yields_nothing(self):
        self.assertEqual(list(proto.frames(b"")), [])

    def test_a_complete_frame_survives_a_truncated_one(self):
        """Whatever arrived whole is still delivered."""
        buf = CAPTURED_BATTERY_FRAME + CAPTURED_CRC_FRAME[:5]
        decoded = list(proto.frames(buf))
        self.assertEqual(len(decoded), 1)
        self.assertEqual(decoded[0][0], EVENT_BATTERY_CHANGED)

    def test_resyncs_past_leading_garbage(self):
        """Bytes before the first 0x55 are skipped, not fatal."""
        decoded = list(proto.frames(b"\xde\xad\xbe\xef" + CAPTURED_BATTERY_FRAME))
        self.assertEqual(len(decoded), 1)
        self.assertEqual(decoded[0][0], EVENT_BATTERY_CHANGED)


class Describe(unittest.TestCase):
    def test_names_a_known_command(self):
        self.assertEqual(proto.describe(EVENT_BATTERY_CHANGED),
                         "EVENT_BATTERY_CHANGED")

    def test_marks_an_unknown_command(self):
        self.assertIn("unknown", proto.describe(0x0BAD))


if __name__ == "__main__":
    unittest.main()
