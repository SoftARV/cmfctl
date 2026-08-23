#!/usr/bin/env python3
"""Attempt a host->device ANC write and confirm via the device's own notification.

Tries candidate set-commands one at a time, waiting for a 0x03E0 ANC-state
notification after each. Restores the starting mode at the end.
"""
import sys, socket, threading, time, queue
sys.path.insert(0, '.')
import proto

CH = 28
ANC_STATE = 0x03E0

events = queue.Queue()
state = {"mode": None}

def reader(sock):
    buf = b""
    while True:
        try:
            d = sock.recv(4096)
        except OSError:
            return
        if not d:
            return
        buf += d
        for cmd, fsn, pl, ok in proto.frames(buf):
            if cmd == ANC_STATE and len(pl) >= 2:
                state["mode"] = pl[1]
                events.put(("anc", pl[1], pl))
            else:
                events.put(("other", cmd, pl))
        buf = b""

def drain(t=1.0):
    end = time.time() + t
    out = []
    while time.time() < end:
        try:
            out.append(events.get(timeout=0.1))
        except queue.Empty:
            pass
    return out

def name(m):
    return proto.ANC_MODES.get(m, f"0x{m:02x}")

MAC = proto.find_device()
s = proto.connect(MAC, CH, timeout=None)
threading.Thread(target=reader, args=(s,), daemon=True).start()

print("listening 3s to learn the current mode...")
for kind, a, pl in drain(3.0):
    print(f"   {kind} {a if kind=='anc' else hex(a)} {proto.hexdump(pl)}")
start_mode = state["mode"]
print(f"start mode: {name(start_mode) if start_mode is not None else 'unknown'}\n")

TARGET = 0x07 if start_mode != 0x07 else 0x01   # flip to something different
print(f"goal: switch to {name(TARGET)}\n")

candidates = [
    ("Ear-line setter 0x0FF0, flags=0x60 target=0x01", 0x0FF0, bytes([0x01, TARGET, 0x00]), 0x60, 0x01),
    ("notify id 0x03E0, flags=0x60 target=0x01",       0x03E0, bytes([0x01, TARGET, 0x00]), 0x60, 0x01),
    ("notify id 0x03E0, flags=0x60 target=0x03",       0x03E0, bytes([0x01, TARGET, 0x00]), 0x60, 0x03),
    ("notify id 0x03E0 full payload, flags=0x60",      0x03E0,
     bytes([0x01, TARGET, 0x00, 0x02, 0x01, 0x00]), 0x60, 0x03),
]

winner = None
for label, cmd, payload, flags, target in candidates:
    pkt = proto.build(cmd, payload, fsn=0x01, flags=flags, target=target)
    print(f"--> {label}")
    print(f"    {proto.hexdump(pkt)}")
    before = state["mode"]
    try:
        s.send(pkt)
    except OSError as e:
        print(f"    send failed: {e}\n")
        continue
    evs = drain(2.5)
    for kind, a, pl in evs:
        print(f"    <- {kind} {a if kind=='anc' else hex(a)} {proto.hexdump(pl)}")
    if state["mode"] == TARGET and before != TARGET:
        print(f"    *** ACCEPTED — mode is now {name(state['mode'])} ***\n")
        winner = (label, cmd, payload, flags, target)
        break
    print(f"    no change (mode still {name(state['mode']) if state['mode'] is not None else '?'})\n")

print("=" * 60)
if winner:
    print(f"SET COMMAND FOUND: {winner[0]}")
    print(f"  cmd=0x{winner[1]:04X} payload={proto.hexdump(winner[2])} "
          f"flags=0x{winner[3]:02x} target=0x{winner[4]:02x}")
    if start_mode is not None and start_mode != TARGET:
        print(f"\nrestoring original mode ({name(start_mode)})...")
        _, cmd, _, flags, target = winner
        s.send(proto.build(cmd, bytes([0x01, start_mode, 0x00]), fsn=0x02,
                           flags=flags, target=target))
        drain(2.0)
        print(f"mode now: {name(state['mode'])}")
else:
    print("No candidate worked. The device did not report a mode change.")
s.close()
