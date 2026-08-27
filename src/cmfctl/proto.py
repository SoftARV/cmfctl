r"""Nothing / CMF RFCOMM protocol primitives.

Frame layout (community-reverse-engineered, CRC verified against published
Nothing Ear (2) captures):

    55 60 01 | cmd_hi cmd_lo | len_lo len_hi | fsn | payload... | crc_lo crc_hi
    \___ magic ___/            \__ u16 LE __/   \seq/             \ CRC-16/MODBUS /

CRC-16/MODBUS: init 0xFFFF, poly 0xA001 (reflected), appended little-endian,
computed over every byte from the magic through the end of the payload.
"""
import errno
import socket
import subprocess
import struct
import time

import constants

# Byte 0 is always 0x55. Byte 1 is a flags byte that decides whether a CRC is
# appended: 0x60 -> CRC present, 0x00 -> no CRC. Byte 2 varies (0x01/0x03/0x06)
# and looks like a target/stream id. Observed on a CMF Headphone Pro, RFCOMM 28.
SYNC = 0x55
FLAG_CRC = 0x60
HDR_LEN = 8          # sync(1) + flags(1) + target(1) + cmd(2) + len(2) + fsn(1)
CRC_LEN = 2

# The command id is LITTLE-endian on the wire. Names come from Nothing X's own
# ProtocolConstant table -- see constants.py.
# DeviceNoiseReduction (com.nothing.earbase.anc.entity) names these
# MODE_NOISE_REDUCTION_STRONG / MEDIUM / WEAK / SMART_1 / CLOSE / PASS_THROUGH.
# 6 (COMFORTABLE) and 8 (SMART_2) exist in the app but this model rejects them.
ANC_MODES = {
    0x01: "high",
    0x02: "mid",
    0x03: "low",
    0x04: "adaptive",
    0x05: "off",
    0x07: "transparency",
}
COMMANDS = dict(constants.ALL)


def describe(cmd):
    """Name a command id, resolving responses back to their request."""
    if cmd in COMMANDS:
        return COMMANDS[cmd]
    req = cmd | 0x8000
    if req in COMMANDS:
        return COMMANDS[req] + " (response)"
    return f"unknown 0x{cmd:04X}"


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def build(cmd: int, payload: bytes = b"", fsn: int = 0x01,
          flags: int = FLAG_CRC, target: int = 0x01) -> bytes:
    body = (bytes([SYNC, flags, target]) + struct.pack("<H", cmd)
            + struct.pack("<H", len(payload)) + bytes([fsn]) + payload)
    if flags & FLAG_CRC:
        body += struct.pack("<H", crc16_modbus(body))
    return body


def frames(buf: bytes):
    """Yield (cmd, fsn, payload, crc_ok) per frame. crc_ok is None if absent."""
    i = 0
    while i + HDR_LEN <= len(buf):
        if buf[i] != SYNC:
            i += 1
            continue
        flags = buf[i + 1]
        cmd = struct.unpack("<H", buf[i + 3:i + 5])[0]
        plen = struct.unpack("<H", buf[i + 5:i + 7])[0]
        has_crc = bool(flags & FLAG_CRC)
        end = i + HDR_LEN + plen + (CRC_LEN if has_crc else 0)
        if end > len(buf):
            break
        fsn = buf[i + 7]
        payload = buf[i + HDR_LEN:i + HDR_LEN + plen]
        if has_crc:
            got = struct.unpack("<H", buf[end - CRC_LEN:end])[0]
            ok = got == crc16_modbus(buf[i:end - CRC_LEN])
        else:
            ok = None          # no CRC on this variant
        yield cmd, fsn, payload, ok
        i = end


def find_device() -> str:
    """Address of the connected CMF/Nothing device.

    Auto-detected rather than hardcoded, so these tools work on any unit.
    """
    out = subprocess.run(["bluetoothctl", "devices", "Connected"],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and any(k in parts[2].lower() for k in ("cmf", "nothing")):
            return parts[1]
    raise SystemExit("No connected CMF/Nothing device found. Connect it first.")


def connect(mac: str, channel: int, timeout: float = 4.0,
            retries: int = 6) -> socket.socket:
    """Open an RFCOMM channel.

    The kernel keeps the channel briefly after close, so back-to-back
    invocations hit EBUSY. Retry with a short backoff rather than failing.
    """
    delay = 0.3
    for attempt in range(retries):
        s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM,
                          socket.BTPROTO_RFCOMM)
        s.settimeout(timeout)
        try:
            s.connect((mac, channel))
            return s
        except OSError as e:
            s.close()
            if e.errno not in (errno.EBUSY, errno.EAGAIN) or attempt == retries - 1:
                raise
            time.sleep(delay)
            delay = min(delay * 1.6, 2.0)
    raise OSError("unreachable")


def hexdump(b: bytes) -> str:
    return " ".join(f"{x:02x}" for x in b)


def ascii_of(b: bytes) -> str:
    return "".join(chr(x) if 32 <= x < 127 else "." for x in b)
