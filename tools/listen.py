#!/usr/bin/env python3
"""Passively log every frame the headphones send. Sends nothing at all.

    ./listen.py [--mac AA:BB:..] [--channel 28] [--log capture.log]

Leave it running and operate the physical controls — roller, Energy Slider,
ANC button. Each notification the device emits is decoded and appended to the
log, which is how we map command IDs without guessing.
"""
import argparse
import datetime
import socket
import os
import sys

# proto lives in the package next door; resolve through any symlink so this
# runs from a checkout reached by one.
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "src"))
from cmfctl import proto

DEFAULT_CH = 28


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mac", help="device address; auto-detected when omitted")
    ap.add_argument("--channel", type=int, default=DEFAULT_CH)
    ap.add_argument("--log", default="capture.log")
    a = ap.parse_args()

    mac = a.mac or proto.find_device()
    s = proto.connect(mac, a.channel, timeout=None)
    log = open(a.log, "a", buffering=1)

    def emit(line):
        print(line, flush=True)
        log.write(line + "\n")

    emit(f"# connected ch{a.channel} at {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    buf = b""
    try:
        while True:
            data = s.recv(4096)
            if not data:
                emit("# peer closed")
                break
            ts = f"{datetime.datetime.now():%H:%M:%S.%f}"[:-3]
            emit(f"[{ts}] raw {proto.hexdump(data)}")
            buf += data
            consumed = 0
            for cmd, fsn, pl, ok in proto.frames(buf):
                consumed = 1
                emit(f"[{ts}]     cmd=0x{cmd:04X} fsn=0x{fsn:02X} "
                     f"crc={'ok' if ok else 'BAD'} len={len(pl)} "
                     f"payload={proto.hexdump(pl) or '-'} |{proto.ascii_of(pl)}|")
            if consumed:
                buf = b""
    except KeyboardInterrupt:
        emit("# stopped")
    finally:
        s.close()
        log.close()


if __name__ == "__main__":
    main()
