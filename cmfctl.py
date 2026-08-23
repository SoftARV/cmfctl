#!/usr/bin/env python3
"""cmfctl — control a CMF Headphone Pro from Linux.

    ./cmfctl.py battery
    ./cmfctl.py anc                 # read current mode
    ./cmfctl.py anc transparency    # set: anc | off | transparency
    ./cmfctl.py get  <COMMAND_NAME>         # any Query command, read-only
    ./cmfctl.py set  <COMMAND_NAME> <hex>   # any Set command
    ./cmfctl.py status [--json]     # everything, over one connection
    ./cmfctl.py features            # what this model supports
    ./cmfctl.py dump                # query every feature, see what answers
    ./cmfctl.py listen              # stream notifications until Ctrl-C
    ./cmfctl.py probe               # scan RFCOMM channels
    ./cmfctl.py codec               # active A2DP codec + whether LDAC is offered

Talks the Nothing protocol over Bluetooth Classic RFCOMM. See FINDINGS.md.
"""
import argparse
import queue
import re
import subprocess
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import constants
import proto

CHANNEL = 28

# Resolved from the app's own table rather than transcribed by hand -- a
# hand-typed id silently produces a command the device just ignores.
_C = constants.BY_NAME
CMD_SET_ANC = _C["SET_CURRENT_NOISE_REDUCTION"]
CMD_SET_LHDC = _C["SET_LHDC_COMMANDS"]        # kept: `set SET_LHDC_COMMANDS 01`
CMD_GET_LHDC = _C["GET_LHDC_COMMANDS"]
NOTIFY_ANC = 0xE003           # EVENT_NOISE_REDUCTION_LEVEL_CHANGED
NOTIFY_BATTERY = 0xE001       # EVENT_BATTERY_CHANGED
MODE_BY_NAME = {"anc": 0x01, "on": 0x01, "off": 0x05, "transparency": 0x07}


find_device = proto.find_device


class Link:
    """RFCOMM link with a background reader, so notifications aren't missed."""

    def __init__(self, mac, channel=CHANNEL):
        self.mac = mac
        self.sock = proto.connect(mac, channel, timeout=None)
        self.events = queue.Queue()
        self.anc = None
        self.battery = None
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        buf = b""
        while True:
            try:
                data = self.sock.recv(4096)
            except OSError:
                return
            if not data:
                return
            buf += data
            for cmd, fsn, pl, ok in proto.frames(buf):
                if cmd == NOTIFY_ANC and len(pl) >= 2:
                    self.anc = pl[1]
                elif cmd == NOTIFY_BATTERY and len(pl) >= 3:
                    self.battery = pl[2]
                self.events.put((cmd, fsn, pl, ok))
            buf = b""

    def send(self, cmd, payload, fsn=0x01, flags=0x60, target=0x01):
        self.sock.send(proto.build(cmd, payload, fsn=fsn, flags=flags, target=target))

    def wait_for(self, predicate, timeout=5.0):
        end = time.time() + timeout
        while time.time() < end:
            if predicate():
                return True
            time.sleep(0.05)
        return False

    def close(self):
        self.sock.close()


def mode_name(m):
    return proto.ANC_MODES.get(m, f"unknown(0x{m:02x})") if m is not None else "unknown"


def read_battery(link):
    """Query the battery directly.

    The device also pushes EVENT_BATTERY_CHANGED, but only every ~10s — far too
    slow for a bar widget. GET_REMOTE_BATTERY_LEVEL answers immediately.
    """
    pl = _query(link, _C["GET_REMOTE_BATTERY_LEVEL"])
    if pl and len(pl) >= 3:
        return pl[2]
    return link.battery


def cmd_battery(link, _):
    pct = read_battery(link)
    if pct is None:
        sys.exit("no battery reading")
    print(f"{pct}%")


def cmd_anc(link, args):
    if not args.mode:
        if link.wait_for(lambda: link.anc is not None, timeout=5):
            print(mode_name(link.anc))
        else:
            sys.exit("no ANC state reported; try toggling the button once")
        return
    want = MODE_BY_NAME.get(args.mode.lower())
    if want is None:
        sys.exit(f"unknown mode {args.mode!r}; use: anc | off | transparency")
    link.send(CMD_SET_ANC, bytes([0x01, want, 0x00]))
    if link.wait_for(lambda: link.anc == want, timeout=5):
        print(mode_name(link.anc))
    else:
        sys.exit(f"device did not confirm the change (still {mode_name(link.anc)})")



def _await_cmd(link, cmd, timeout):
    end = time.time() + timeout
    while time.time() < end:
        try:
            c, fsn, pl, ok = link.events.get(timeout=0.2)
        except queue.Empty:
            continue
        if c == cmd:
            return pl
    return None


# Queries that look like they start a process rather than read a value.
DUMP_SKIP = {"GET_HEADTRACK_START"}


def cmd_dump(link, args):
    """Send every Query command and report what the device answers.

    Read-only: the 0xC000 range is reads by design. Anything the device does
    not implement simply goes unanswered, so this maps the supported feature
    set in one pass.
    """
    answered, silent = [], []
    items = sorted(constants.QUERY.items())
    for i, (cmd, name) in enumerate(items, 1):
        if name in DUMP_SKIP:
            continue
        while not link.events.empty():          # clear async noise
            link.events.get()
        link.send(cmd, b"", fsn=i & 0xFF)
        pl = _await_cmd(link, cmd & ~0x8000, args.timeout)
        if pl is None:
            silent.append(name)
        else:
            answered.append((cmd, name, pl))
            print(f"  {name:<42} {proto.hexdump(pl) or '(empty)'}")

    print(f"\n{len(answered)} answered, {len(silent)} silent "
          f"(silent = not supported on this model)")
    if args.verbose and silent:
        print("\nsilent:")
        for n in silent:
            print(f"  {n}")


def _query(link, get_cmd, timeout=4.0):
    link.send(get_cmd, b"")
    return _await_cmd(link, get_cmd & ~0x8000, timeout)


def _apply(link, set_cmd, payload, get_cmd, timeout=4.0):
    link.send(set_cmd, payload)
    if _await_cmd(link, set_cmd & ~0x8000, timeout) is None:
        sys.exit("device did not acknowledge the change")
    return _query(link, get_cmd)





def cmd_features(link, args):
    """Decode what this model actually supports.

    GET_SUPPORTED_FEATURE is a little-endian bitmap; GET_EXTRA_FEATURE_STATUS
    is a count byte followed by (feature_id, enabled) pairs.
    """
    pl = _query(link, _C["GET_SUPPORTED_FEATURE"])
    if pl is not None:
        val = int.from_bytes(pl, "little")
        print(f"supported features (0x{val:08X}):")
        for bit, name in sorted(constants.SUPPORT_FEATURE_BITS.items()):
            if val & bit:
                print(f"  + {name}")
        if args.verbose:
            for bit, name in sorted(constants.SUPPORT_FEATURE_BITS.items()):
                if not val & bit:
                    print(f"  - {name}")

    pl = _query(link, _C["GET_EXTRA_FEATURE_STATUS"])
    if pl is not None and len(pl) >= 1:
        count = pl[0]
        print(f"\ntoggleable features ({count}):")
        for i in range(1, min(len(pl) - 1, count * 2), 2):
            fid, enabled = pl[i], pl[i + 1]
            name = constants.EXTRA_FEATURE_IDS.get(fid, f"unknown-{fid}")
            print(f"  {name:<20} {'on' if enabled else 'off'}")


def cmd_status(link, args):
    """Everything a UI needs, over a single RFCOMM connection.

    Opening the link dominates the cost, so gathering state in one go is what
    makes polling from a bar widget viable.
    """
    anc = _query(link, _C["GET_CURRENT_NOISE_REDUCTION"])
    ldac = _query(link, CMD_GET_LHDC)

    # The negotiated codec is not the same thing as the LDAC flag: the flag says
    # the headphones will *offer* LDAC, while the codec is what host and device
    # actually agreed on. Reading it costs no Bluetooth -- it comes from
    # PipeWire -- so report both and let callers show the truth.
    codec, offered, _profile = a2dp_state(link.mac)

    state = {
        "battery": read_battery(link),
        "anc": mode_name(anc[1]) if anc and len(anc) > 1 else None,
        "ldac": bool(ldac[-1]) if ldac else None,
        "codec": codec,
        "codecs": offered or None,
    }
    if args.json:
        import json
        print(json.dumps(state))
    else:
        for k, v in state.items():
            print(f"  {k:<14} {v}")


def cmd_get(link, args):
    """Send any Query command by name. Read-only."""
    name = args.name.upper()
    if name not in constants.BY_NAME:
        sys.exit(f"unknown command {name!r}; see constants.py")
    cmd = constants.BY_NAME[name]
    if not (0xC000 <= cmd < 0xE000):
        sys.exit(f"{name} is not a Query command (0x{cmd:04X})")
    pl = _query(link, cmd)
    print(proto.hexdump(pl) if pl is not None else "(no reply — unsupported)")


def cmd_set(link, args):
    """Send any Set command by name with an explicit hex payload."""
    name = args.name.upper()
    if name not in constants.BY_NAME:
        sys.exit(f"unknown command {name!r}; see constants.py")
    cmd = constants.BY_NAME[name]
    if not (0xF000 <= cmd <= 0xFFFF):
        sys.exit(f"{name} is not a Set command (0x{cmd:04X})")
    payload = bytes.fromhex(args.payload.replace(":", " ").replace(" ", ""))
    link.send(cmd, payload)
    ack = _await_cmd(link, cmd & ~0x8000, 4.0)
    print(f"ack: {proto.hexdump(ack) if ack is not None else '(none)'}")


def cmd_listen(link, _):
    print("streaming notifications, Ctrl-C to stop")
    try:
        while True:
            cmd, fsn, pl, ok = link.events.get()
            label = proto.describe(cmd)
            crc = "" if ok is None else (" crc=ok" if ok else " crc=BAD")
            print(f"cmd=0x{cmd:04X} {label:<22} payload={proto.hexdump(pl) or '-'}{crc}")
    except KeyboardInterrupt:
        pass


def a2dp_state(mac):
    """Ask PipeWire what codec is live and which A2DP codecs the device offers.

    A2DP capabilities are exchanged when the link is established, so this
    reflects what the headphones advertised at connect time — which is exactly
    what a device-side LDAC toggle changes.
    """
    card = "bluez_card." + mac.replace(":", "_")
    txt = subprocess.run(["pactl", "list", "cards"], capture_output=True, text=True).stdout
    block, grab = [], False
    for line in txt.splitlines():
        if line.strip().startswith("Name: "):
            grab = card in line
        if grab:
            block.append(line)
    # PipeWire gives the highest-priority codec the bare "a2dp-sink" name, so the
    # profile name does not identify the codec -- read it from the description.
    offered, active = [], None
    for line in block:
        t = line.strip()
        if t.startswith("a2dp-sink"):
            m = re.search(r"codec ([A-Za-z0-9\-_]+)", t)
            offered.append(m.group(1) if m else t.split(":")[0])
        elif t.startswith("Active Profile:"):
            active = t.split(":", 1)[1].strip()

    codec = None
    dump = subprocess.run(["pw-dump"], capture_output=True, text=True).stdout
    try:
        import json
        for o in json.loads(dump):
            p = (o.get("info") or {}).get("props") or {}
            if p.get("api.bluez5.address") == mac and "api.bluez5.codec" in p:
                codec = p["api.bluez5.codec"]
    except Exception:
        pass
    return codec, offered, active


def cmd_codec(_, args):
    mac = args.mac or find_device()
    codec, offered, active = a2dp_state(mac)
    print(f"active codec   : {codec or 'unknown'}")
    print(f"active profile : {active or 'unknown'}")
    print(f"a2dp offered   : {', '.join(offered) if offered else 'none'}")
    has_ldac = any("ldac" in o.lower() for o in offered)
    print(f"LDAC advertised: {'YES' if has_ldac else 'no'}")
    if not has_ldac:
        print("\n  The headphones are not offering LDAC. PipeWire can do it")
        print("  (libspa-codec-bluez5-ldac.so + libldac are installed), so this")
        print("  reflects the device-side toggle being off — try './cmfctl.py ldac on'.")



def cmd_probe(_, args):
    mac = args.mac or find_device()
    print(f"scanning RFCOMM channels on {mac}")
    for ch in range(1, 31):
        try:
            s = proto.connect(mac, ch, timeout=1.5)
        except OSError:
            continue
        print(f"  channel {ch:2}: open" + ("  <- Nothing protocol" if ch == CHANNEL else ""))
        s.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mac", help="override device address")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("battery")
    a = sub.add_parser("anc"); a.add_argument("mode", nargs="?")
    stt = sub.add_parser("status"); stt.add_argument("--json", action="store_true")
    fe = sub.add_parser("features"); fe.add_argument("-v", "--verbose", action="store_true")
    g = sub.add_parser("get"); g.add_argument("name")
    st = sub.add_parser("set"); st.add_argument("name"); st.add_argument("payload")
    d = sub.add_parser("dump")
    d.add_argument("--timeout", type=float, default=0.6)
    d.add_argument("-v", "--verbose", action="store_true")
    sub.add_parser("listen")
    sub.add_parser("probe")
    sub.add_parser("codec")
    args = ap.parse_args()

    if args.cmd == "probe":
        return cmd_probe(None, args)
    if args.cmd == "codec":
        return cmd_codec(None, args)

    mac = args.mac or find_device()
    link = Link(mac)
    try:
        {"battery": cmd_battery, "anc": cmd_anc,
         "get": cmd_get, "set": cmd_set, "features": cmd_features,
         "status": cmd_status,
         "dump": cmd_dump, "listen": cmd_listen}[args.cmd](link, args)
    finally:
        link.close()


if __name__ == "__main__":
    main()
